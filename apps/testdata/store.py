"""In-memory store for test data bundles with TTL."""

import asyncio
import hashlib
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import logging

from .models import TestDataBundle, TestDataMeta, ArtifactInfo

logger = logging.getLogger(__name__)

# Configuration
TTL_HOURS = int(os.getenv("TESTDATA_TTL_HOURS", "24"))
CLEANUP_INTERVAL_MINUTES = int(os.getenv("TESTDATA_CLEANUP_INTERVAL_MINUTES", "60"))


class TestDataStore:
    """Process-local in-memory store for test data bundles."""
    
    def __init__(self):
        self._store: Dict[str, TestDataBundle] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._started = False
    
    async def start_cleanup_task(self):
        """Start the background cleanup task."""
        if not self._started:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._started = True
            logger.info(f"Started testdata cleanup task (interval: {CLEANUP_INTERVAL_MINUTES}m, TTL: {TTL_HOURS}h)")
    
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
        self._store[testdata_id] = bundle
        logger.info(f"Stored test data bundle {testdata_id} (expires: {bundle.expires_at})")
        return testdata_id
    
    def get_bundle(self, testdata_id: str) -> Optional[TestDataBundle]:
        """Retrieve a test data bundle by ID."""
        bundle = self._store.get(testdata_id)
        if bundle is None:
            return None
        
        # Check if expired
        if datetime.utcnow() > bundle.expires_at:
            self._store.pop(testdata_id, None)
            logger.info(f"Removed expired test data bundle {testdata_id}")
            return None
        
        return bundle
    
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
            present=bundle.schema is not None,
            count=1 if bundle.schema else None,
            sha256=self._get_sha256(bundle.raw_payloads.get("schema")) if bundle.schema else None
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
    schema=None,
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
        schema=schema,
        raw_payloads=raw_payloads or {}
    )
