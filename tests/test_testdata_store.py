"""Tests for test data store functionality."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch
from apps.testdata.store import TestDataStore, create_bundle, get_store
from apps.testdata.models import PassageRecord, QARecord


class TestTestDataStore:
    """Test TestDataStore functionality."""
    
    @pytest.fixture
    def store(self):
        """Create a fresh test data store."""
        return TestDataStore()
    
    @pytest.fixture
    def sample_bundle(self):
        """Create a sample test data bundle."""
        passages = [
            PassageRecord(id="1", text="First passage", meta=None),
            PassageRecord(id="2", text="Second passage", meta=None)
        ]
        qaset = [
            QARecord(qid="1", question="What is AI?", expected_answer="Technology", contexts=None),
            QARecord(qid="2", question="What is ML?", expected_answer="Machine Learning", contexts=None)
        ]
        return create_bundle(
            passages=passages,
            qaset=qaset,
            raw_payloads={"passages": "raw passages", "qaset": "raw qaset"}
        )
    
    def test_store_and_retrieve_bundle(self, store, sample_bundle):
        """Test storing and retrieving a bundle."""
        # Store bundle
        testdata_id = store.put_bundle(sample_bundle)
        assert testdata_id == sample_bundle.testdata_id
        
        # Retrieve bundle
        retrieved = store.get_bundle(testdata_id)
        assert retrieved is not None
        assert retrieved.testdata_id == testdata_id
        assert len(retrieved.passages) == 2
        assert len(retrieved.qaset) == 2
    
    def test_get_nonexistent_bundle(self, store):
        """Test retrieving a non-existent bundle."""
        result = store.get_bundle("nonexistent-id")
        assert result is None
    
    def test_get_meta(self, store, sample_bundle):
        """Test getting metadata for a bundle."""
        # Store bundle
        testdata_id = store.put_bundle(sample_bundle)
        
        # Get metadata
        meta = store.get_meta(testdata_id)
        assert meta is not None
        assert meta.testdata_id == testdata_id
        assert meta.artifacts["passages"].present is True
        assert meta.artifacts["passages"].count == 2
        assert meta.artifacts["qaset"].present is True
        assert meta.artifacts["qaset"].count == 2
        assert meta.artifacts["attacks"].present is False
        assert meta.artifacts["schema"].present is False
    
    def test_get_meta_nonexistent(self, store):
        """Test getting metadata for non-existent bundle."""
        meta = store.get_meta("nonexistent-id")
        assert meta is None
    
    def test_remove_bundle(self, store, sample_bundle):
        """Test removing a bundle."""
        # Store bundle
        testdata_id = store.put_bundle(sample_bundle)
        assert store.get_bundle(testdata_id) is not None
        
        # Remove bundle
        result = store.remove_bundle(testdata_id)
        assert result is True
        
        # Verify removal
        assert store.get_bundle(testdata_id) is None
        
        # Remove again (should return False)
        result = store.remove_bundle(testdata_id)
        assert result is False
    
    def test_list_bundles(self, store, sample_bundle):
        """Test listing bundles."""
        # Initially empty
        bundles = store.list_bundles()
        assert len(bundles) == 0
        
        # Store bundle
        testdata_id = store.put_bundle(sample_bundle)
        
        # List bundles
        bundles = store.list_bundles()
        assert len(bundles) == 1
        assert testdata_id in bundles
        assert isinstance(bundles[testdata_id], datetime)
    
    def test_cleanup_expired(self, store):
        """Test cleanup of expired bundles."""
        # Create an expired bundle
        expired_bundle = create_bundle(
            passages=[PassageRecord(id="1", text="test", meta=None)]
        )
        # Manually set expiration to past
        expired_bundle.expires_at = datetime.utcnow() - timedelta(hours=1)
        
        # Create a valid bundle
        valid_bundle = create_bundle(
            qaset=[QARecord(qid="1", question="test?", expected_answer="yes", contexts=None)]
        )
        
        # Store both
        expired_id = store.put_bundle(expired_bundle)
        valid_id = store.put_bundle(valid_bundle)
        
        # Verify both exist initially
        assert len(store.list_bundles()) == 2
        
        # Clean up expired
        cleaned = store.cleanup_expired()
        assert cleaned == 1
        
        # Verify only valid bundle remains
        bundles = store.list_bundles()
        assert len(bundles) == 1
        assert valid_id in bundles
        assert expired_id not in bundles
    
    def test_get_expired_bundle_returns_none(self, store):
        """Test that getting an expired bundle returns None and removes it."""
        # Create an expired bundle
        expired_bundle = create_bundle(
            passages=[PassageRecord(id="1", text="test", meta=None)]
        )
        expired_bundle.expires_at = datetime.utcnow() - timedelta(hours=1)
        
        # Store it
        testdata_id = store.put_bundle(expired_bundle)
        
        # Try to get it (should return None and remove it)
        result = store.get_bundle(testdata_id)
        assert result is None
        
        # Verify it's been removed
        assert len(store.list_bundles()) == 0
    
    def test_sha256_calculation(self, store):
        """Test SHA256 calculation for content."""
        from apps.testdata.store import TestDataStore
        
        # Test with known content
        content = "test content"
        expected_hash = "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"
        
        result = TestDataStore._get_sha256(content)
        assert result == expected_hash
        
        # Test with None
        result = TestDataStore._get_sha256(None)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cleanup_task_lifecycle(self, store):
        """Test starting and stopping the cleanup task."""
        # Initially not started
        assert store._started is False
        assert store._cleanup_task is None
        
        # Start cleanup task
        await store.start_cleanup_task()
        assert store._started is True
        assert store._cleanup_task is not None
        
        # Stop cleanup task
        await store.stop_cleanup_task()
        assert store._started is False
        assert store._cleanup_task is None


class TestBundleCreation:
    """Test bundle creation utilities."""
    
    def test_create_bundle_minimal(self):
        """Test creating a minimal bundle."""
        bundle = create_bundle()
        
        assert bundle.testdata_id is not None
        assert bundle.created_at is not None
        assert bundle.expires_at > bundle.created_at
        assert bundle.passages is None
        assert bundle.qaset is None
        assert bundle.attacks is None
        assert bundle.json_schema is None
    
    def test_create_bundle_with_data(self):
        """Test creating a bundle with data."""
        passages = [PassageRecord(id="1", text="test", meta=None)]
        qaset = [QARecord(qid="1", question="test?", expected_answer="yes", contexts=None)]
        attacks = ["attack1", "attack2"]
        schema = {"type": "object"}
        raw_payloads = {"passages": "raw"}
        
        bundle = create_bundle(
            passages=passages,
            qaset=qaset,
            attacks=attacks,
            json_schema=schema,
            raw_payloads=raw_payloads
        )
        
        assert bundle.passages == passages
        assert bundle.qaset == qaset
        assert bundle.attacks == attacks
        assert bundle.json_schema == schema
        assert bundle.raw_payloads == raw_payloads
    
    def test_create_bundle_id_uniqueness(self):
        """Test that bundle IDs are unique."""
        from apps.testdata.store import create_bundle_id
        
        id1 = create_bundle_id()
        id2 = create_bundle_id()
        
        assert id1 != id2
        assert len(id1) > 0
        assert len(id2) > 0


class TestGlobalStore:
    """Test global store functionality."""
    
    def test_get_store_singleton(self):
        """Test that get_store returns the same instance."""
        store1 = get_store()
        store2 = get_store()
        
        assert store1 is store2
    
    @pytest.mark.asyncio
    async def test_start_stop_store(self):
        """Test starting and stopping the global store."""
        from apps.testdata.store import start_store, stop_store
        
        # Start store
        await start_store()
        store = get_store()
        assert store._started is True
        
        # Stop store
        await stop_store()
        assert store._started is False
    
    def test_store_configuration(self):
        """Test store uses environment configuration."""
        # Import after setting environment to ensure config is read correctly
        with patch.dict('os.environ', {'TESTDATA_TTL_HOURS': '48'}):
            # Force reimport to pick up the new environment variable
            import importlib
            import apps.testdata.store
            importlib.reload(apps.testdata.store)
            from apps.testdata.store import create_bundle
            
            bundle = create_bundle()
            expected_expiry = bundle.created_at + timedelta(hours=48)
            
            # Allow for small time difference due to execution time
            time_diff = abs((bundle.expires_at - expected_expiry).total_seconds())
            assert time_diff < 1.0  # Less than 1 second difference
