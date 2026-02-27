"""
Unit tests for Event Bus.

Tests the core functionality of the event bus including subscription,
publishing, retry logic, and event logging.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models.schemas import Event, EventType
from backend.orchestrator.event_bus import EventBus


@pytest.fixture
def event_bus():
    """Create a fresh event bus for each test."""
    return EventBus()


@pytest.fixture
def sample_event():
    """Create a sample event for testing."""
    return Event(
        event_type=EventType.VIP_DETECTED,
        payload={"vip_id": "test-vip-123", "confidence": 0.95},
        source_agent="identity_agent",
        vip_id="test-vip-123"
    )


class TestEventBusSubscription:
    """Test event subscription functionality."""
    
    def test_subscribe_handler(self, event_bus):
        """Test subscribing a handler to an event type."""
        handler = MagicMock()
        
        event_bus.subscribe(EventType.VIP_DETECTED, handler)
        
        assert event_bus.get_subscription_count(EventType.VIP_DETECTED) == 1
    
    def test_subscribe_multiple_handlers(self, event_bus):
        """Test subscribing multiple handlers to the same event type."""
        handler1 = MagicMock()
        handler2 = MagicMock()
        
        event_bus.subscribe(EventType.VIP_DETECTED, handler1)
        event_bus.subscribe(EventType.VIP_DETECTED, handler2)
        
        assert event_bus.get_subscription_count(EventType.VIP_DETECTED) == 2
    
    def test_subscribe_same_handler_twice(self, event_bus):
        """Test that subscribing the same handler twice doesn't duplicate it."""
        handler = MagicMock()
        
        event_bus.subscribe(EventType.VIP_DETECTED, handler)
        event_bus.subscribe(EventType.VIP_DETECTED, handler)
        
        assert event_bus.get_subscription_count(EventType.VIP_DETECTED) == 1
    
    def test_unsubscribe_handler(self, event_bus):
        """Test unsubscribing a handler from an event type."""
        handler = MagicMock()
        
        event_bus.subscribe(EventType.VIP_DETECTED, handler)
        event_bus.unsubscribe(EventType.VIP_DETECTED, handler)
        
        assert event_bus.get_subscription_count(EventType.VIP_DETECTED) == 0


class TestEventBusPublish:
    """Test event publishing functionality."""
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_publish_to_single_subscriber(self, mock_session, event_bus, sample_event):
        """Test publishing event to a single subscriber."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        handler = AsyncMock()
        event_bus.subscribe(EventType.VIP_DETECTED, handler)
        
        await event_bus.publish(sample_event)
        
        handler.assert_called_once_with(sample_event)
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_publish_to_multiple_subscribers(self, mock_session, event_bus, sample_event):
        """Test publishing event to multiple subscribers."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        handler1 = AsyncMock()
        handler2 = AsyncMock()
        
        event_bus.subscribe(EventType.VIP_DETECTED, handler1)
        event_bus.subscribe(EventType.VIP_DETECTED, handler2)
        
        await event_bus.publish(sample_event)
        
        handler1.assert_called_once_with(sample_event)
        handler2.assert_called_once_with(sample_event)
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_publish_with_no_subscribers(self, mock_session, event_bus, sample_event):
        """Test publishing event when there are no subscribers."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Should not raise an error
        await event_bus.publish(sample_event)
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_publish_with_handler_error(self, mock_session, event_bus, sample_event):
        """Test that handler errors don't prevent other handlers from receiving events."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        failing_handler = AsyncMock(side_effect=Exception("Handler error"))
        working_handler = AsyncMock()
        
        event_bus.subscribe(EventType.VIP_DETECTED, failing_handler)
        event_bus.subscribe(EventType.VIP_DETECTED, working_handler)
        
        await event_bus.publish(sample_event)
        
        # Both handlers should be called despite the first one failing
        failing_handler.assert_called_once()
        working_handler.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_publish_logs_event_to_database(self, mock_session, event_bus, sample_event):
        """Test that publishing an event logs it to the database."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        await event_bus.publish(sample_event)
        
        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()


class TestEventBusPublishWithRetry:
    """Test event publishing with retry logic."""
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_publish_with_retry_success_on_first_attempt(self, mock_session, event_bus, sample_event):
        """Test successful delivery on first attempt."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        handler = AsyncMock()
        event_bus.subscribe(EventType.VIP_DETECTED, handler)
        
        await event_bus.publish_with_retry(sample_event, max_retries=3)
        
        # Should be called exactly once (no retries needed)
        handler.assert_called_once_with(sample_event)
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_publish_with_retry_success_on_second_attempt(self, mock_session, event_bus, sample_event):
        """Test successful delivery after one retry."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Fail once, then succeed
        handler = AsyncMock(side_effect=[Exception("Temporary error"), None])
        event_bus.subscribe(EventType.VIP_DETECTED, handler)
        
        await event_bus.publish_with_retry(sample_event, max_retries=3, base_delay=0.01)
        
        # Should be called twice (initial + 1 retry)
        assert handler.call_count == 2
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_publish_with_retry_max_retries_exceeded(self, mock_session, event_bus, sample_event):
        """Test that retries stop after max_retries is reached."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Always fail
        handler = AsyncMock(side_effect=Exception("Permanent error"))
        event_bus.subscribe(EventType.VIP_DETECTED, handler)
        
        await event_bus.publish_with_retry(sample_event, max_retries=3, base_delay=0.01)
        
        # Should be called 4 times (initial + 3 retries)
        assert handler.call_count == 4
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_publish_with_retry_exponential_backoff(self, mock_session, event_bus, sample_event):
        """Test that exponential backoff delays are applied."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Fail twice, then succeed
        handler = AsyncMock(side_effect=[
            Exception("Error 1"),
            Exception("Error 2"),
            None
        ])
        event_bus.subscribe(EventType.VIP_DETECTED, handler)
        
        start_time = asyncio.get_event_loop().time()
        await event_bus.publish_with_retry(sample_event, max_retries=3, base_delay=0.1)
        end_time = asyncio.get_event_loop().time()
        
        # Should have delays: 0.1s (after 1st retry) + 0.2s (after 2nd retry) = 0.3s minimum
        # Allow for small timing variations (0.29s is acceptable)
        elapsed = end_time - start_time
        assert elapsed >= 0.29, f"Expected at least 0.29s delay, got {elapsed}s"
        
        # Should be called 3 times (initial + 2 retries)
        assert handler.call_count == 3


class TestEventBusHistory:
    """Test event history functionality."""
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_get_event_history_all(self, mock_session, event_bus):
        """Test retrieving all events from history."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        event1 = Event(
            event_type=EventType.VIP_DETECTED,
            payload={},
            source_agent="agent1",
            vip_id="vip1"
        )
        event2 = Event(
            event_type=EventType.ESCORT_ASSIGNED,
            payload={},
            source_agent="agent2",
            vip_id="vip2"
        )
        
        await event_bus.publish(event1)
        await event_bus.publish(event2)
        
        history = event_bus.get_event_history()
        assert len(history) == 2
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_get_event_history_filtered_by_vip(self, mock_session, event_bus):
        """Test retrieving events filtered by VIP ID."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        event1 = Event(
            event_type=EventType.VIP_DETECTED,
            payload={},
            source_agent="agent1",
            vip_id="vip1"
        )
        event2 = Event(
            event_type=EventType.ESCORT_ASSIGNED,
            payload={},
            source_agent="agent2",
            vip_id="vip2"
        )
        event3 = Event(
            event_type=EventType.BUGGY_DISPATCHED,
            payload={},
            source_agent="agent3",
            vip_id="vip1"
        )
        
        await event_bus.publish(event1)
        await event_bus.publish(event2)
        await event_bus.publish(event3)
        
        history = event_bus.get_event_history(vip_id="vip1")
        assert len(history) == 2
        assert all(e.vip_id == "vip1" for e in history)
    
    def test_clear_history(self, event_bus):
        """Test clearing event history."""
        event_bus._event_history = [MagicMock(), MagicMock()]
        
        event_bus.clear_history()
        
        assert len(event_bus.get_event_history()) == 0


class TestEventBusSupportedEventTypes:
    """Test that all defined event types are supported."""
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_all_event_types_supported(self, mock_session, event_bus):
        """Test that the event bus accepts all defined event types."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        handler = AsyncMock()
        
        # Subscribe to all event types
        for event_type in EventType:
            event_bus.subscribe(event_type, handler)
        
        # Publish events of each type
        for event_type in EventType:
            event = Event(
                event_type=event_type,
                payload={},
                source_agent="test_agent",
                vip_id="test-vip"
            )
            await event_bus.publish(event)
        
        # Verify all events were delivered
        assert handler.call_count == len(EventType)
