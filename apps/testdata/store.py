"""In-memory store for test data bundles with TTL and Redis backing."""

import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any, cast, TYPE_CHECKING

if TYPE_CHECKING:
    import redis.asyncio as redis
import logging

from .models import TestDataBundle, TestDataMeta, ArtifactInfo, PassageRecord, QARecord

logger = logging.getLogger(__name__)

# Configuration
TTL_HOURS = int(os.getenv("TESTDATA_TTL_HOURS", "24"))
CLEANUP_INTERVAL_MINUTES = int(os.getenv("TESTDATA_CLEANUP_INTERVAL_MINUTES", "60"))
REDIS_URL = os.getenv("REDIS_URL")
REDIS_PREFIX = os.getenv("REDIS_PREFIX", "aqk:")


class TestDataStore:
    """Hybrid Redis/in-memory store for test data bundles."""
    
    def __init__(self):
        self._store: Dict[str, TestDataBundle] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._started = False
        self._redis: Optional["redis.Redis"] = None
        self._redis_available = False
    
    async def start_cleanup_task(self):
        """Start the background cleanup task and initialize Redis if available."""
        if not self._started:
            # Try to initialize Redis
            await self._init_redis()
            
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._started = True
            storage_type = "Redis" if self._redis_available else "in-memory"
            logger.info(f"Started testdata cleanup task using {storage_type} storage (interval: {CLEANUP_INTERVAL_MINUTES}m, TTL: {TTL_HOURS}h)")
    
    async def _init_redis(self):
        """Initialize Redis connection if available."""
        if not REDIS_URL:
            logger.info("No REDIS_URL configured, using in-memory storage only")
            return
            
        try:
            import redis.asyncio as redis
            self._redis = redis.from_url(REDIS_URL, decode_responses=True)
            # Test connection
            await self._redis.ping()
            self._redis_available = True
            logger.info(f"Connected to Redis for test data storage: {REDIS_URL}")
        except ImportError:
            logger.warning("Redis library not installed. Install with: pip install redis")
            self._redis_available = False
        except Exception as e:
            logger.warning(f"Failed to connect to Redis, falling back to in-memory: {e}")
            self._redis_available = False
    
    def _get_payload_key(self, testdata_id: str) -> str:
        """Get Redis key for test data payloads."""
        return f"{REDIS_PREFIX}testdata:{testdata_id}:payloads"
    
    def _get_meta_key(self, testdata_id: str) -> str:
        """Get Redis key for test data metadata."""
        return f"{REDIS_PREFIX}testdata:{testdata_id}:meta"
    
    async def stop_cleanup_task(self):
        """Stop the background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            self._started = False
            logger.info("Stopped testdata cleanup task")
    
    def put_bundle(self, bundle: TestDataBundle) -> str:
        """Store a test data bundle and return its ID."""
        testdata_id = bundle.testdata_id
        
        # Store in memory
        self._store[testdata_id] = bundle
        
        # Also store in Redis if available
        if self._redis_available:
            asyncio.create_task(self._put_bundle_redis(bundle))
        
        logger.info(f"Stored test data bundle {testdata_id} (expires: {bundle.expires_at})")
        return testdata_id
    
    async def _put_bundle_redis(self, bundle: TestDataBundle):
        """Store bundle in Redis asynchronously."""
        if not self._redis:
            return
            
        try:
            testdata_id = bundle.testdata_id
            ttl_seconds = TTL_HOURS * 3600
            
            # Prepare payload data
            payload_data = {}
            if bundle.passages:
                payload_data["passages"] = json.dumps([p.model_dump() for p in bundle.passages])
            if bundle.qaset:
                payload_data["qaset"] = json.dumps([q.model_dump() for q in bundle.qaset])
            if bundle.attacks:
                payload_data["attacks"] = json.dumps(bundle.attacks)  
            if bundle.json_schema:
                payload_data["schema"] = json.dumps(bundle.json_schema)
            
            # Add raw payloads
            for key, value in bundle.raw_payloads.items():
                payload_data[f"raw_{key}"] = value
            
            # Prepare metadata
            meta_data = {
                "created_at": bundle.created_at.isoformat(),
                "expires_at": bundle.expires_at.isoformat(),
                "testdata_id": testdata_id
            }
            
            # Store in Redis with TTL
            payload_key = self._get_payload_key(testdata_id)
            meta_key = self._get_meta_key(testdata_id)
            
            async with self._redis.pipeline() as pipe:
                # Store payloads
                if payload_data:
                    pipe.hset(payload_key, mapping=cast(Any, payload_data))
                    pipe.expire(payload_key, ttl_seconds)
                
                # Store metadata  
                pipe.hset(meta_key, mapping=cast(Any, meta_data))
                pipe.expire(meta_key, ttl_seconds)
                
                await pipe.execute()
                
            logger.debug(f"Stored bundle {testdata_id} in Redis")
            
        except Exception as e:
            logger.error(f"Failed to store bundle {bundle.testdata_id} in Redis: {e}")
            # Don't raise - memory storage already succeeded
    
    def get_bundle(self, testdata_id: str) -> Optional[TestDataBundle]:
        """Retrieve a test data bundle by ID."""
        # First check memory
        bundle = self._store.get(testdata_id)
        if bundle is not None:
            # Check if expired
            if datetime.utcnow() > bundle.expires_at:
                self._store.pop(testdata_id, None)
                logger.info(f"Removed expired test data bundle {testdata_id}")
                return None
            return bundle
        
        # If not in memory and Redis is available, try Redis
        if self._redis_available:
            try:
                bundle = asyncio.run(self._get_bundle_redis(testdata_id))
                if bundle is not None:
                    # Store in memory for faster future access
                    self._store[testdata_id] = bundle
                    return bundle
            except Exception as e:
                logger.error(f"Failed to retrieve bundle {testdata_id} from Redis: {e}")
        
        return None
    
    async def _get_bundle_redis(self, testdata_id: str) -> Optional[TestDataBundle]:
        """Retrieve bundle from Redis."""
        if not self._redis:
            return None
            
        try:
            payload_key = self._get_payload_key(testdata_id)
            meta_key = self._get_meta_key(testdata_id)
            
            # Check if exists
            if not await self._redis.exists(meta_key):
                return None
            
            # Get metadata and payload data
            meta_data = await self._redis.hgetall(meta_key)  # type: ignore
            payload_data = await self._redis.hgetall(payload_key)  # type: ignore
            
            if not meta_data:
                return None
            
            # Parse metadata
            created_at = datetime.fromisoformat(meta_data["created_at"])
            expires_at = datetime.fromisoformat(meta_data["expires_at"])
            
            # Check if expired
            if datetime.utcnow() > expires_at:
                logger.info(f"Removed expired test data bundle {testdata_id} from Redis")
                return None
            
            # Parse payload data
            passages = None
            qaset = None  
            attacks = None
            schema = None
            raw_payloads = {}
            
            for key, value in payload_data.items():
                if key.startswith("raw_"):
                    raw_payloads[key[4:]] = value  # Remove "raw_" prefix
                elif key in ["passages", "qaset", "attacks", "schema"]:
                    try:
                        parsed_value = json.loads(value)
                        if key == "passages":
                            passages = [PassageRecord(**p) for p in parsed_value]
                        elif key == "qaset":
                            qaset = [QARecord(**q) for q in parsed_value]
                        elif key == "attacks":
                            attacks = parsed_value
                        elif key == "schema":
                            schema = parsed_value
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse {key} data for bundle {testdata_id}")
                    except Exception as e:
                        logger.warning(f"Failed to reconstruct {key} objects for bundle {testdata_id}: {e}")
            
            # Create bundle
            bundle = TestDataBundle(
                testdata_id=testdata_id,
                created_at=created_at,
                expires_at=expires_at,
                passages=passages,
                qaset=qaset,
                attacks=attacks,
                json_schema=schema,
                raw_payloads=raw_payloads
            )
            
            return bundle
            
        except Exception as e:
            logger.error(f"Failed to retrieve bundle {testdata_id} from Redis: {e}")
            return None
    
    def get_meta(self, testdata_id: str) -> Optional[TestDataMeta]:
        """Get metadata for a test data bundle."""
        bundle = self.get_bundle(testdata_id)
        if bundle is None:
            return None
        
        artifacts = {}
        
        # Passages
        artifacts["passages"] = ArtifactInfo(
            present=bundle.passages is not None,
            count=len(bundle.passages) if bundle.passages else None,
            sha256=self._get_sha256(bundle.raw_payloads.get("passages")) if bundle.passages else None
        )
        
        # QA Set
        artifacts["qaset"] = ArtifactInfo(
            present=bundle.qaset is not None,
            count=len(bundle.qaset) if bundle.qaset else None,
            sha256=self._get_sha256(bundle.raw_payloads.get("qaset")) if bundle.qaset else None
        )
        
        # Attacks
        artifacts["attacks"] = ArtifactInfo(
            present=bundle.attacks is not None,
            count=len(bundle.attacks) if bundle.attacks else None,
            sha256=self._get_sha256(bundle.raw_payloads.get("attacks")) if bundle.attacks else None
        )
        
        # Schema
        artifacts["schema"] = ArtifactInfo(
            present=bundle.json_schema is not None,
            count=1 if bundle.json_schema else None,
            sha256=self._get_sha256(bundle.raw_payloads.get("schema")) if bundle.json_schema else None
        )
        
        return TestDataMeta(
            testdata_id=testdata_id,
            created_at=bundle.created_at,
            expires_at=bundle.expires_at,
            artifacts=artifacts
        )
    
    def remove_bundle(self, testdata_id: str) -> bool:
        """Remove a test data bundle."""
        return self._store.pop(testdata_id, None) is not None
    
    def list_bundles(self) -> Dict[str, datetime]:
        """List all bundles with their expiration times (for debugging)."""
        return {tid: bundle.expires_at for tid, bundle in self._store.items()}
    
    def cleanup_expired(self) -> int:
        """Remove expired bundles and return count removed."""
        now = datetime.utcnow()
        expired_ids = [
            tid for tid, bundle in self._store.items()
            if now > bundle.expires_at
        ]
        
        for tid in expired_ids:
            del self._store[tid]
        
        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired test data bundles")
        
        return len(expired_ids)
    
    @staticmethod
    def _get_sha256(content: Optional[str]) -> Optional[str]:
        """Get SHA256 hash of content."""
        if content is None:
            return None
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    async def _cleanup_loop(self):
        """Background task to clean up expired bundles."""
        while True:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL_MINUTES * 60)
                self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in testdata cleanup task: {e}")


# Global store instance
_store: Optional[TestDataStore] = None


def get_store() -> TestDataStore:
    """Get the global test data store instance."""
    global _store
    if _store is None:
        _store = TestDataStore()
    return _store


async def start_store():
    """Start the test data store and cleanup task."""
    store = get_store()
    await store.start_cleanup_task()


async def stop_store():
    """Stop the test data store and cleanup task."""
    store = get_store()
    await store.stop_cleanup_task()


def create_bundle_id() -> str:
    """Generate a new test data bundle ID."""
    return str(uuid.uuid4())


def create_bundle(
    passages=None,
    qaset=None,
    attacks=None,
    json_schema=None,
    raw_payloads=None
) -> TestDataBundle:
    """Create a new test data bundle with expiration."""
    now = datetime.utcnow()
    expires_at = now + timedelta(hours=TTL_HOURS)
    
    return TestDataBundle(
        testdata_id=create_bundle_id(),
        created_at=now,
        expires_at=expires_at,
        passages=passages,
        qaset=qaset,
        attacks=attacks,
        json_schema=json_schema,
        raw_payloads=raw_payloads or {}
    )
