"""
Integration tests for WebSocket Manager and Event Bus.

Tests the integration between WebSocket Manager and Event Bus to ensure
events are properly pushed to WebSocket clients within 500ms.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models.schemas import Event, EventType
from backend.orchestrator.event_bus import EventBus
from backend.websocket.manager import WebSocketManager


@pytest.fixture
def event_bus():
    """Create a fresh event bus for each test."""
    return EventBus()


@pytest.fixture
def ws_manager():
    """Create a fresh WebSocket manager for each test."""
    return WebSocketManager()


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


class TestWebSocketEventBusIntegration:
    """Test integration between WebSocket Manager and Event Bus."""
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_event_bus_pushes_to_websocket(self, mock_session, event_bus, ws_manager, mock_websocket):
        """Test that Event Bus events are pushed to WebSocket clients."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Connect WebSocket client
        await ws_manager.connect(mock_websocket)
        
        # Subscribe WebSocket manager to all event types
        for event_type in EventType:
            event_bus.subscribe(event_type, ws_manager.handle_event)
        
        # Publish an event
        event = Event(
            event_type=EventType.VIP_DETECTED,
            payload={"confidence": 0.95},
            source_agent="identity_agent",
            vip_id="test-vip-123"
        )
        
        await event_bus.publish(event)
        
        # Verify WebSocket client received the message
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "vip_update"
        assert call_args["payload"]["event_type"] == "vip_detected"
        assert call_args["payload"]["vip_id"] == "test-vip-123"
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_multiple_events_pushed_to_websocket(self, mock_session, event_bus, ws_manager, mock_websocket):
        """Test that multiple events are pushed to WebSocket clients."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Connect WebSocket client
        await ws_manager.connect(mock_websocket)
        
        # Subscribe WebSocket manager to all event types
        for event_type in EventType:
            event_bus.subscribe(event_type, ws_manager.handle_event)
        
        # Publish multiple events
        events = [
            Event(event_type=EventType.VIP_DETECTED, payload={}, source_agent="agent1", vip_id="vip1"),
            Event(event_type=EventType.ESCORT_ASSIGNED, payload={}, source_agent="agent2", vip_id="vip1"),
            Event(event_type=EventType.BUGGY_DISPATCHED, payload={}, source_agent="agent3", vip_id="vip1"),
        ]
        
        for event in events:
            await event_bus.publish(event)
        
        # Verify all events were sent to WebSocket client
        assert mock_websocket.send_json.call_count == 3
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_event_pushed_to_multiple_websocket_clients(self, mock_session, event_bus, ws_manager):
        """Test that events are pushed to all connected WebSocket clients."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Connect multiple WebSocket clients
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()
        
        await ws_manager.connect(ws1)
        await ws_manager.connect(ws2)
        await ws_manager.connect(ws3)
        
        # Subscribe WebSocket manager to event bus
        event_bus.subscribe(EventType.VIP_DETECTED, ws_manager.handle_event)
        
        # Publish an event
        event = Event(
            event_type=EventType.VIP_DETECTED,
            payload={"confidence": 0.95},
            source_agent="identity_agent",
            vip_id="test-vip-123"
        )
        
        await event_bus.publish(event)
        
        # Verify all clients received the message
        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()
        ws3.send_json.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_websocket_update_latency(self, mock_session, event_bus, ws_manager, mock_websocket):
        """Test that WebSocket updates are pushed within 500ms of event occurrence."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Connect WebSocket client
        await ws_manager.connect(mock_websocket)
        
        # Subscribe WebSocket manager to event bus
        event_bus.subscribe(EventType.VIP_DETECTED, ws_manager.handle_event)
        
        # Publish an event and measure latency
        event = Event(
            event_type=EventType.VIP_DETECTED,
            payload={"confidence": 0.95},
            source_agent="identity_agent",
            vip_id="test-vip-123"
        )
        
        start_time = asyncio.get_event_loop().time()
        await event_bus.publish(event)
        end_time = asyncio.get_event_loop().time()
        
        # Verify latency is within 500ms
        latency_ms = (end_time - start_time) * 1000
        assert latency_ms < 500, f"WebSocket update latency {latency_ms}ms exceeds 500ms requirement"
        
        # Verify message was sent
        mock_websocket.send_json.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_all_event_types_pushed_to_websocket(self, mock_session, event_bus, ws_manager, mock_websocket):
        """Test that all event types are properly pushed to WebSocket clients."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Connect WebSocket client
        await ws_manager.connect(mock_websocket)
        
        # Subscribe WebSocket manager to all event types
        for event_type in EventType:
            event_bus.subscribe(event_type, ws_manager.handle_event)
        
        # Publish events of each type
        for event_type in EventType:
            event = Event(
                event_type=event_type,
                payload={},
                source_agent="test_agent",
                vip_id="test-vip"
            )
            await event_bus.publish(event)
        
        # Verify all events were sent to WebSocket client
        assert mock_websocket.send_json.call_count == len(EventType)
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_websocket_receives_correct_message_format(self, mock_session, event_bus, ws_manager, mock_websocket):
        """Test that WebSocket messages have the correct format."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Connect WebSocket client
        await ws_manager.connect(mock_websocket)
        
        # Subscribe WebSocket manager to event bus
        event_bus.subscribe(EventType.ESCORT_ASSIGNED, ws_manager.handle_event)
        
        # Publish an event
        event = Event(
            event_type=EventType.ESCORT_ASSIGNED,
            payload={"escort_id": "escort-1", "escort_name": "John Doe"},
            source_agent="escort_agent",
            vip_id="test-vip-123",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        await event_bus.publish(event)
        
        # Verify message format
        mock_websocket.send_json.assert_called_once()
        message = mock_websocket.send_json.call_args[0][0]
        
        # Check required fields
        assert "type" in message
        assert "payload" in message
        assert "timestamp" in message
        
        # Check message type
        assert message["type"] == "escort_update"
        
        # Check payload structure
        assert message["payload"]["event_type"] == "escort_assigned"
        assert message["payload"]["vip_id"] == "test-vip-123"
        assert message["payload"]["source_agent"] == "escort_agent"
        assert message["payload"]["escort_id"] == "escort-1"
        assert message["payload"]["escort_name"] == "John Doe"
        
        # Check timestamp format (ISO 8601)
        assert message["timestamp"] == "2024-01-01T12:00:00+00:00"
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_websocket_manager_handles_event_bus_errors(self, mock_session, event_bus, ws_manager):
        """Test that WebSocket manager handles Event Bus errors gracefully."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        # Connect a failing WebSocket client
        failing_ws = AsyncMock()
        failing_ws.send_json = AsyncMock(side_effect=Exception("Connection error"))
        
        await ws_manager.connect(failing_ws)
        
        # Subscribe WebSocket manager to event bus
        event_bus.subscribe(EventType.VIP_DETECTED, ws_manager.handle_event)
        
        # Publish an event - should not raise an error
        event = Event(
            event_type=EventType.VIP_DETECTED,
            payload={},
            source_agent="identity_agent",
            vip_id="test-vip-123"
        )
        
        await event_bus.publish(event)
        
        # Verify failing client was disconnected
        assert ws_manager.get_connection_count() == 0


class TestWebSocketMessageTypeMapping:
    """Test that Event Bus events map to correct WebSocket message types."""
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_vip_events_map_to_vip_update(self, mock_session, event_bus, ws_manager, mock_websocket):
        """Test that VIP-related events map to vip_update message type."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        await ws_manager.connect(mock_websocket)
        
        vip_event_types = [
            EventType.VIP_DETECTED,
            EventType.STATE_CHANGED,
            EventType.BAGGAGE_PRIORITY_TAGGED,
        ]
        
        for event_type in vip_event_types:
            event_bus.subscribe(event_type, ws_manager.handle_event)
            
            event = Event(
                event_type=event_type,
                payload={},
                source_agent="test_agent",
                vip_id="test-vip"
            )
            
            await event_bus.publish(event)
            
            # Verify message type
            call_args = mock_websocket.send_json.call_args[0][0]
            assert call_args["type"] == "vip_update", f"{event_type} should map to vip_update"
            
            mock_websocket.send_json.reset_mock()
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_escort_events_map_to_escort_update(self, mock_session, event_bus, ws_manager, mock_websocket):
        """Test that escort events map to escort_update message type."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        await ws_manager.connect(mock_websocket)
        event_bus.subscribe(EventType.ESCORT_ASSIGNED, ws_manager.handle_event)
        
        event = Event(
            event_type=EventType.ESCORT_ASSIGNED,
            payload={},
            source_agent="escort_agent",
            vip_id="test-vip"
        )
        
        await event_bus.publish(event)
        
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "escort_update"
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_buggy_events_map_to_buggy_update(self, mock_session, event_bus, ws_manager, mock_websocket):
        """Test that buggy events map to buggy_update message type."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        await ws_manager.connect(mock_websocket)
        event_bus.subscribe(EventType.BUGGY_DISPATCHED, ws_manager.handle_event)
        
        event = Event(
            event_type=EventType.BUGGY_DISPATCHED,
            payload={},
            source_agent="transport_agent",
            vip_id="test-vip"
        )
        
        await event_bus.publish(event)
        
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "buggy_update"
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_lounge_events_map_to_lounge_update(self, mock_session, event_bus, ws_manager, mock_websocket):
        """Test that lounge events map to lounge_update message type."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        await ws_manager.connect(mock_websocket)
        
        lounge_event_types = [
            EventType.LOUNGE_RESERVED,
            EventType.LOUNGE_ENTRY,
        ]
        
        for event_type in lounge_event_types:
            event_bus.subscribe(event_type, ws_manager.handle_event)
            
            event = Event(
                event_type=event_type,
                payload={},
                source_agent="lounge_agent",
                vip_id="test-vip"
            )
            
            await event_bus.publish(event)
            
            call_args = mock_websocket.send_json.call_args[0][0]
            assert call_args["type"] == "lounge_update", f"{event_type} should map to lounge_update"
            
            mock_websocket.send_json.reset_mock()
    
    @pytest.mark.asyncio
    @patch('backend.orchestrator.event_bus.SessionLocal')
    async def test_flight_events_map_to_flight_update(self, mock_session, event_bus, ws_manager, mock_websocket):
        """Test that flight events map to flight_update message type."""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        await ws_manager.connect(mock_websocket)
        
        flight_event_types = [
            EventType.FLIGHT_DELAY,
            EventType.BOARDING_ALERT,
        ]
        
        for event_type in flight_event_types:
            event_bus.subscribe(event_type, ws_manager.handle_event)
            
            event = Event(
                event_type=event_type,
                payload={},
                source_agent="flight_intelligence_agent",
                vip_id="test-vip"
            )
            
            await event_bus.publish(event)
            
            call_args = mock_websocket.send_json.call_args[0][0]
            assert call_args["type"] == "flight_update", f"{event_type} should map to flight_update"
            
            mock_websocket.send_json.reset_mock()
