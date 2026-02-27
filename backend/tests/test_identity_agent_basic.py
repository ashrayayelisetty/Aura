"""
Basic unit tests for Identity Agent (without DeepFace dependency).

These tests verify the agent structure and basic functionality.
Full tests with DeepFace mocking are in test_identity_agent.py
"""

import numpy as np
import pytest

from backend.models.schemas import EventType
from backend.orchestrator.event_bus import EventBus


class TestIdentityAgentStructure:
    """Test Identity Agent structure without requiring DeepFace."""
    
    def test_identity_agent_can_be_imported(self):
        """Test that Identity Agent can be imported."""
        try:
            from backend.agents.identity_agent import IdentityAgent
            assert IdentityAgent is not None
        except ImportError as e:
            pytest.skip(f"DeepFace not installed: {e}")
    
    def test_identity_agent_initialization(self):
        """Test that Identity Agent initializes correctly."""
        try:
            from backend.agents.identity_agent import IdentityAgent
            
            event_bus = EventBus()
            agent = IdentityAgent(event_bus)
            
            # Verify initialization
            assert agent.event_bus is event_bus
            assert agent.confidence_threshold == 0.85
            assert agent.model_name == "VGG-Face"
            assert agent.frame_rate == 2
            assert agent.camera_width == 640
            assert agent.camera_height == 480
            assert agent.camera is None
            assert agent._running is False
            
        except ImportError as e:
            pytest.skip(f"DeepFace not installed: {e}")
    
    def test_cosine_similarity_method_exists(self):
        """Test that cosine similarity method exists and works."""
        try:
            from backend.agents.identity_agent import IdentityAgent
            
            event_bus = EventBus()
            agent = IdentityAgent(event_bus)
            
            # Test with identical vectors
            vec1 = np.array([1.0, 0.0, 0.0])
            vec2 = np.array([1.0, 0.0, 0.0])
            
            similarity = agent._cosine_similarity(vec1, vec2)
            
            # Identical vectors should have similarity close to 1.0
            assert 0.99 <= similarity <= 1.0
            
        except ImportError as e:
            pytest.skip(f"DeepFace not installed: {e}")
    
    def test_agent_has_required_methods(self):
        """Test that agent has all required methods."""
        try:
            from backend.agents.identity_agent import IdentityAgent
            
            event_bus = EventBus()
            agent = IdentityAgent(event_bus)
            
            # Verify all required methods exist
            assert hasattr(agent, 'extract_embedding')
            assert callable(agent.extract_embedding)
            
            assert hasattr(agent, 'match_vip')
            assert callable(agent.match_vip)
            
            assert hasattr(agent, 'process_camera_feed')
            assert callable(agent.process_camera_feed)
            
            assert hasattr(agent, 'stop')
            assert callable(agent.stop)
            
            assert hasattr(agent, '_cosine_similarity')
            assert callable(agent._cosine_similarity)
            
        except ImportError as e:
            pytest.skip(f"DeepFace not installed: {e}")


class TestCosineSimilarityCalculation:
    """Test cosine similarity calculation without DeepFace."""
    
    def test_identical_vectors(self):
        """Test cosine similarity with identical vectors."""
        try:
            from backend.agents.identity_agent import IdentityAgent
            
            event_bus = EventBus()
            agent = IdentityAgent(event_bus)
            
            vec = np.random.rand(128)
            similarity = agent._cosine_similarity(vec, vec)
            
            assert 0.99 <= similarity <= 1.0
            
        except ImportError as e:
            pytest.skip(f"DeepFace not installed: {e}")
    
    def test_orthogonal_vectors(self):
        """Test cosine similarity with orthogonal vectors."""
        try:
            from backend.agents.identity_agent import IdentityAgent
            
            event_bus = EventBus()
            agent = IdentityAgent(event_bus)
            
            vec1 = np.zeros(128)
            vec1[0] = 1.0
            
            vec2 = np.zeros(128)
            vec2[1] = 1.0
            
            similarity = agent._cosine_similarity(vec1, vec2)
            
            # Orthogonal vectors should have similarity around 0.5
            assert 0.4 <= similarity <= 0.6
            
        except ImportError as e:
            pytest.skip(f"DeepFace not installed: {e}")
    
    def test_opposite_vectors(self):
        """Test cosine similarity with opposite vectors."""
        try:
            from backend.agents.identity_agent import IdentityAgent
            
            event_bus = EventBus()
            agent = IdentityAgent(event_bus)
            
            vec1 = np.ones(128)
            vec2 = -np.ones(128)
            
            similarity = agent._cosine_similarity(vec1, vec2)
            
            # Opposite vectors should have similarity close to 0.0
            assert 0.0 <= similarity <= 0.1
            
        except ImportError as e:
            pytest.skip(f"DeepFace not installed: {e}")
