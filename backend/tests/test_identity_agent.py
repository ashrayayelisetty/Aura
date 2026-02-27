"""
Unit tests for Identity Agent.

Tests face recognition, VIP matching, and event emission.
"""

import asyncio
import pickle
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from backend.agents.identity_agent import IdentityAgent
from backend.models.schemas import Event, EventType
from backend.orchestrator.event_bus import EventBus
from backend.database.models import VIPProfileDB


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus()


@pytest.fixture
def identity_agent(event_bus):
    """Create an identity agent for testing."""
    return IdentityAgent(event_bus)


@pytest.fixture
def sample_embedding():
    """Create a sample 128-dimensional face embedding."""
    return np.random.rand(128).astype(np.float64)


@pytest.fixture
def sample_face_image():
    """Create a sample face image (640x480 BGR)."""
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)


class TestIdentityAgentInitialization:
    """Test Identity Agent initialization."""
    
    def test_initialization(self, identity_agent):
        """Test that agent initializes with correct configuration."""
        assert identity_agent.event_bus is not None
        assert identity_agent.confidence_threshold == 0.85
        assert identity_agent.model_name == "VGG-Face"
        assert identity_agent.frame_rate == 2
        assert identity_agent.camera_width == 640
        assert identity_agent.camera_height == 480
        assert identity_agent.camera is None
        assert identity_agent._running is False


class TestEmbeddingExtraction:
    """Test face embedding extraction."""
    
    @pytest.mark.asyncio
    async def test_extract_embedding_success(self, identity_agent, sample_face_image):
        """Test successful embedding extraction."""
        # Mock DeepFace.represent to return a sample embedding
        mock_embedding = np.random.rand(128).tolist()
        
        with patch("backend.agents.identity_agent.DeepFace.represent") as mock_represent:
            mock_represent.return_value = [{"embedding": mock_embedding}]
            
            embedding = await identity_agent.extract_embedding(sample_face_image)
            
            assert isinstance(embedding, np.ndarray)
            assert embedding.shape == (128,)
            mock_represent.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_extract_embedding_no_face(self, identity_agent, sample_face_image):
        """Test embedding extraction when no face is detected."""
        with patch("backend.agents.identity_agent.DeepFace.represent") as mock_represent:
            mock_represent.return_value = []
            
            with pytest.raises(ValueError, match="No face detected"):
                await identity_agent.extract_embedding(sample_face_image)
    
    @pytest.mark.asyncio
    async def test_extract_embedding_exception(self, identity_agent, sample_face_image):
        """Test embedding extraction when DeepFace raises an exception."""
        with patch("backend.agents.identity_agent.DeepFace.represent") as mock_represent:
            mock_represent.side_effect = Exception("DeepFace error")
            
            with pytest.raises(ValueError, match="Face embedding extraction failed"):
                await identity_agent.extract_embedding(sample_face_image)


class TestCosineSimilarity:
    """Test cosine similarity calculation."""
    
    def test_cosine_similarity_identical(self, identity_agent):
        """Test cosine similarity with identical embeddings."""
        embedding = np.random.rand(128)
        similarity = identity_agent._cosine_similarity(embedding, embedding)
        
        # Identical embeddings should have similarity close to 1.0
        assert 0.99 <= similarity <= 1.0
    
    def test_cosine_similarity_different(self, identity_agent):
        """Test cosine similarity with different embeddings."""
        embedding1 = np.random.rand(128)
        embedding2 = np.random.rand(128)
        
        similarity = identity_agent._cosine_similarity(embedding1, embedding2)
        
        # Different embeddings should have similarity between 0 and 1
        assert 0.0 <= similarity <= 1.0
    
    def test_cosine_similarity_orthogonal(self, identity_agent):
        """Test cosine similarity with orthogonal embeddings."""
        # Create orthogonal vectors
        embedding1 = np.zeros(128)
        embedding1[0] = 1.0
        
        embedding2 = np.zeros(128)
        embedding2[1] = 1.0
        
        similarity = identity_agent._cosine_similarity(embedding1, embedding2)
        
        # Orthogonal vectors should have similarity close to 0.5 (after normalization)
        assert 0.4 <= similarity <= 0.6


class TestVIPMatching:
    """Test VIP matching against stored profiles."""
    
    @pytest.mark.asyncio
    async def test_match_vip_success(self, identity_agent, sample_embedding):
        """Test successful VIP matching."""
        # Create a mock VIP profile
        vip_id = "test-vip-123"
        stored_embedding = sample_embedding + np.random.rand(128) * 0.01  # Very similar
        
        mock_vip = MagicMock(spec=VIPProfileDB)
        mock_vip.id = vip_id
        mock_vip.name = "Test VIP"
        mock_vip.face_embedding = pickle.dumps(stored_embedding)
        
        with patch("backend.agents.identity_agent.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_db.query.return_value.all.return_value = [mock_vip]
            mock_session.return_value = mock_db
            
            matched_id, confidence = await identity_agent.match_vip(sample_embedding)
            
            assert matched_id == vip_id
            assert confidence > 0.0
    
    @pytest.mark.asyncio
    async def test_match_vip_no_profiles(self, identity_agent, sample_embedding):
        """Test VIP matching when no profiles exist."""
        with patch("backend.agents.identity_agent.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_db.query.return_value.all.return_value = []
            mock_session.return_value = mock_db
            
            matched_id, confidence = await identity_agent.match_vip(sample_embedding)
            
            assert matched_id is None
            assert confidence == 0.0
    
    @pytest.mark.asyncio
    async def test_match_vip_multiple_profiles(self, identity_agent, sample_embedding):
        """Test VIP matching with multiple profiles (returns best match)."""
        # Create mock VIP profiles with different similarities
        vip1_embedding = sample_embedding + np.random.rand(128) * 0.5  # Less similar
        vip2_embedding = sample_embedding + np.random.rand(128) * 0.01  # More similar
        
        mock_vip1 = MagicMock(spec=VIPProfileDB)
        mock_vip1.id = "vip-1"
        mock_vip1.name = "VIP 1"
        mock_vip1.face_embedding = pickle.dumps(vip1_embedding)
        
        mock_vip2 = MagicMock(spec=VIPProfileDB)
        mock_vip2.id = "vip-2"
        mock_vip2.name = "VIP 2"
        mock_vip2.face_embedding = pickle.dumps(vip2_embedding)
        
        with patch("backend.agents.identity_agent.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_db.query.return_value.all.return_value = [mock_vip1, mock_vip2]
            mock_session.return_value = mock_db
            
            matched_id, confidence = await identity_agent.match_vip(sample_embedding)
            
            # Should match VIP 2 (more similar)
            assert matched_id == "vip-2"
            assert confidence > 0.0


class TestConfidenceThreshold:
    """Test confidence threshold checking."""
    
    @pytest.mark.asyncio
    async def test_confidence_above_threshold(self, identity_agent, event_bus, sample_embedding):
        """Test that VIP_DETECTED event is emitted when confidence exceeds threshold."""
        vip_id = "test-vip-123"
        high_confidence = 0.95
        
        # Track published events
        published_events = []
        
        async def capture_event(event: Event):
            published_events.append(event)
        
        event_bus.subscribe(EventType.VIP_DETECTED, capture_event)
        
        # Mock match_vip to return high confidence
        with patch.object(identity_agent, "match_vip", return_value=(vip_id, high_confidence)):
            with patch.object(identity_agent, "extract_embedding", return_value=sample_embedding):
                # Simulate processing a single frame
                with patch("backend.agents.identity_agent.cv2.VideoCapture") as mock_camera:
                    mock_cam_instance = MagicMock()
                    mock_cam_instance.isOpened.return_value = True
                    mock_cam_instance.read.side_effect = [
                        (True, np.zeros((480, 640, 3), dtype=np.uint8)),  # First frame
                        (False, None)  # Stop after first frame
                    ]
                    mock_camera.return_value = mock_cam_instance
                    
                    # Run for a short time
                    task = asyncio.create_task(identity_agent.process_camera_feed())
                    await asyncio.sleep(0.1)
                    identity_agent.stop()
                    
                    try:
                        await asyncio.wait_for(task, timeout=1.0)
                    except asyncio.TimeoutError:
                        pass
        
        # Verify event was published
        assert len(published_events) > 0
        event = published_events[0]
        assert event.event_type == EventType.VIP_DETECTED
        assert event.payload["vip_id"] == vip_id
        assert event.payload["confidence"] == high_confidence
        assert event.vip_id == vip_id
    
    @pytest.mark.asyncio
    async def test_confidence_below_threshold(self, identity_agent, event_bus, sample_embedding):
        """Test that no event is emitted when confidence is below threshold."""
        vip_id = "test-vip-123"
        low_confidence = 0.50  # Below default threshold of 0.85
        
        # Track published events
        published_events = []
        
        async def capture_event(event: Event):
            published_events.append(event)
        
        event_bus.subscribe(EventType.VIP_DETECTED, capture_event)
        
        # Mock match_vip to return low confidence
        with patch.object(identity_agent, "match_vip", return_value=(vip_id, low_confidence)):
            with patch.object(identity_agent, "extract_embedding", return_value=sample_embedding):
                # Simulate processing a single frame
                with patch("backend.agents.identity_agent.cv2.VideoCapture") as mock_camera:
                    mock_cam_instance = MagicMock()
                    mock_cam_instance.isOpened.return_value = True
                    mock_cam_instance.read.side_effect = [
                        (True, np.zeros((480, 640, 3), dtype=np.uint8)),  # First frame
                        (False, None)  # Stop after first frame
                    ]
                    mock_camera.return_value = mock_cam_instance
                    
                    # Run for a short time
                    task = asyncio.create_task(identity_agent.process_camera_feed())
                    await asyncio.sleep(0.1)
                    identity_agent.stop()
                    
                    try:
                        await asyncio.wait_for(task, timeout=1.0)
                    except asyncio.TimeoutError:
                        pass
        
        # Verify no event was published
        assert len(published_events) == 0


class TestCameraFeedProcessing:
    """Test camera feed processing loop."""
    
    @pytest.mark.asyncio
    async def test_camera_initialization_failure(self, identity_agent):
        """Test handling of camera initialization failure."""
        with patch("backend.agents.identity_agent.cv2.VideoCapture") as mock_camera:
            mock_cam_instance = MagicMock()
            mock_cam_instance.isOpened.return_value = False
            mock_camera.return_value = mock_cam_instance
            
            await identity_agent.process_camera_feed()
            
            # Should return early without processing
            assert identity_agent._running is False
    
    @pytest.mark.asyncio
    async def test_stop_camera_feed(self, identity_agent):
        """Test stopping the camera feed processing."""
        with patch("backend.agents.identity_agent.cv2.VideoCapture") as mock_camera:
            mock_cam_instance = MagicMock()
            mock_cam_instance.isOpened.return_value = True
            mock_cam_instance.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
            mock_camera.return_value = mock_cam_instance
            
            # Start processing
            task = asyncio.create_task(identity_agent.process_camera_feed())
            
            # Wait a bit then stop
            await asyncio.sleep(0.1)
            identity_agent.stop()
            
            # Wait for task to complete
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.TimeoutError:
                pass
            
            # Verify camera was released
            mock_cam_instance.release.assert_called_once()
