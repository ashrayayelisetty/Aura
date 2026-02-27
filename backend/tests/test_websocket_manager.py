"""
Unit tests for WebSocket Manager.

Tests the core functionality of the WebSocket manager including connection
management, broadcasting, and Event Bus integration.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.models.schemas import Event, EventType
from backend.websocket.manager import WebSocketManager


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


@pytest.fixture
def sample_event():
    """Create a sample event for testing."""
    return Event(
        event_type=EventType.VIP_DETECTED,
        payload={"vip_id": "test-vip-123", "confidence": 0.95},
        source_agent="identity_agent",
        vip_id="test-vip-123",
        timestamp=datetime.now(timezone.utc)
    )


class TestWebSocketConnection:
    """Test WebSocket connection management."""
    
    @pytest.mark.asyncio
    async def test_connect_single_client(self, ws_manager, mock_websocket):
        """Test connecting a single WebSocket client."""
        await ws_manager.connect(mock_websocket)
        
        mock_websocket.accept.assert_called_once()
        assert ws_manager.get_connection_count() == 1
    
    @pytest.mark.asyncio
    async def test_connect_multiple_clients(self, ws_manager):
        """Test connecting multiple WebSocket clients."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()
        
        await ws_manager.connect(ws1)
        await ws_manager.connect(ws2)
        await ws_manager.connect(ws3)
        
        assert ws_manager.get_connection_count() == 3
    
    @pytest.mark.asyncio
    async def test_disconnect_client(self, ws_manager, mock_websocket):
        """Test disconnecting a WebSocket client."""
        await ws_manager.connect(mock_websocket)
        assert ws_manager.get_connection_count() == 1
        
        await ws_manager.disconnect(mock_websocket)
        assert ws_manager.get_connection_count() == 0
    
    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_client(self, ws_manager, mock_websocket):
        """Test disconnecting a client that was never connected."""
        # Should not raise an error
        await ws_manager.disconnect(mock_websocket)
        assert ws_manager.get_connection_count() == 0
    
    @pytest.mark.asyncio
    async def test_disconnect_already_disconnected_client(self, ws_manager, mock_websocket):
        """Test disconnecting a client twice."""
        await ws_manager.connect(mock_websocket)
        await ws_manager.disconnect(mock_websocket)
        
        # Should not raise an error
        await ws_manager.disconnect(mock_websocket)
        assert ws_manager.get_connection_count() == 0


class TestWebSocketBroadcast:
    """Test WebSocket broadcasting functionality."""
    
    @pytest.mark.asyncio
    async def test_broadcast_to_single_client(self, ws_manager, mock_websocket):
        """Test broadcasting message to a single client."""
        await ws_manager.connect(mock_websocket)
        
        message = {"type": "vip_update", "payload": {"test": "data"}, "timestamp": "2024-01-01T00:00:00Z"}
        await ws_manager.broadcast(message)
        
        mock_websocket.send_json.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_clients(self, ws_manager):
        """Test broadcasting message to multiple clients."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()
        
        await ws_manager.connect(ws1)
        await ws_manager.connect(ws2)
        await ws_manager.connect(ws3)
        
        message = {"type": "vip_update", "payload": {"test": "data"}, "timestamp": "2024-01-01T00:00:00Z"}
        await ws_manager.broadcast(message)
        
        ws1.send_json.assert_called_once_with(message)
        ws2.send_json.assert_called_once_with(message)
        ws3.send_json.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_broadcast_with_no_clients(self, ws_manager):
        """Test broadcasting when no clients are connected."""
        message = {"type": "vip_update", "payload": {"test": "data"}, "timestamp": "2024-01-01T00:00:00Z"}
        
        # Should not raise an error
        await ws_manager.broadcast(message)
    
    @pytest.mark.asyncio
    async def test_broadcast_with_failing_client(self, ws_manager):
        """Test that failing client is disconnected during broadcast."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws2.send_json = AsyncMock(side_effect=Exception("Connection error"))
        ws3 = AsyncMock()
        
        await ws_manager.connect(ws1)
        await ws_manager.connect(ws2)
        await ws_manager.connect(ws3)
        
        message = {"type": "vip_update", "payload": {"test": "data"}, "timestamp": "2024-01-01T00:00:00Z"}
        await ws_manager.broadcast(message)
        
        # ws1 and ws3 should receive the message
        ws1.send_json.assert_called_once_with(message)
        ws3.send_json.assert_called_once_with(message)
        
        # ws2 should be disconnected
        assert ws_manager.get_connection_count() == 2


class TestWebSocketSendToClient:
    """Test sending messages to specific clients."""
    
    @pytest.mark.asyncio
    async def test_send_to_specific_client(self, ws_manager, mock_websocket):
        """Test sending message to a specific client."""
        await ws_manager.connect(mock_websocket)
        
        message = {"type": "vip_update", "payload": {"test": "data"}, "timestamp": "2024-01-01T00:00:00Z"}
        await ws_manager.send_to_client(mock_websocket, message)
        
        mock_websocket.send_json.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_send_to_client_with_error(self, ws_manager):
        """Test that failing client is disconnected when sending fails."""
        ws = AsyncMock()
        ws.send_json = AsyncMock(side_effect=Exception("Connection error"))
        
        await ws_manager.connect(ws)
        assert ws_manager.get_connection_count() == 1
        
        message = {"type": "vip_update", "payload": {"test": "data"}, "timestamp": "2024-01-01T00:00:00Z"}
        await ws_manager.send_to_client(ws, message)
        
        # Client should be disconnected
        assert ws_manager.get_connection_count() == 0


class TestWebSocketMessageCreation:
    """Test WebSocket message creation from Event Bus events."""
    
    def test_create_message_vip_detected(self, ws_manager):
        """Test creating WebSocket message for VIP_DETECTED event."""
        event = Event(
            event_type=EventType.VIP_DETECTED,
            payload={"confidence": 0.95},
            source_agent="identity_agent",
            vip_id="test-vip-123",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        message = ws_manager._create_websocket_message(event)
        
        assert message["type"] == "vip_update"
        assert message["payload"]["event_type"] == "vip_detected"
        assert message["payload"]["vip_id"] == "test-vip-123"
        assert message["payload"]["source_agent"] == "identity_agent"
        assert message["payload"]["confidence"] == 0.95
        assert message["timestamp"] == "2024-01-01T12:00:00+00:00"
    
    def test_create_message_escort_assigned(self, ws_manager):
        """Test creating WebSocket message for ESCORT_ASSIGNED event."""
        event = Event(
            event_type=EventType.ESCORT_ASSIGNED,
            payload={"escort_id": "escort-1", "escort_name": "John Doe"},
            source_agent="escort_agent",
            vip_id="test-vip-123",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        message = ws_manager._create_websocket_message(event)
        
        assert message["type"] == "escort_update"
        assert message["payload"]["event_type"] == "escort_assigned"
        assert message["payload"]["escort_id"] == "escort-1"
    
    def test_create_message_buggy_dispatched(self, ws_manager):
        """Test creating WebSocket message for BUGGY_DISPATCHED event."""
        event = Event(
            event_type=EventType.BUGGY_DISPATCHED,
            payload={"buggy_id": "buggy-1", "destination": "lounge"},
            source_agent="transport_agent",
            vip_id="test-vip-123",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        message = ws_manager._create_websocket_message(event)
        
        assert message["type"] == "buggy_update"
        assert message["payload"]["event_type"] == "buggy_dispatched"
        assert message["payload"]["buggy_id"] == "buggy-1"
    
    def test_create_message_lounge_entry(self, ws_manager):
        """Test creating WebSocket message for LOUNGE_ENTRY event."""
        event = Event(
            event_type=EventType.LOUNGE_ENTRY,
            payload={"reservation_id": "res-1"},
            source_agent="lounge_agent",
            vip_id="test-vip-123",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        message = ws_manager._create_websocket_message(event)
        
        assert message["type"] == "lounge_update"
        assert message["payload"]["event_type"] == "lounge_entry"
    
    def test_create_message_flight_delay(self, ws_manager):
        """Test creating WebSocket message for FLIGHT_DELAY event."""
        event = Event(
            event_type=EventType.FLIGHT_DELAY,
            payload={"flight_id": "FL123", "delay_minutes": 30},
            source_agent="flight_intelligence_agent",
            vip_id="test-vip-123",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        message = ws_manager._create_websocket_message(event)
        
        assert message["type"] == "flight_update"
        assert message["payload"]["event_type"] == "flight_delay"
        assert message["payload"]["delay_minutes"] == 30
    
    def test_create_message_boarding_alert(self, ws_manager):
        """Test creating WebSocket message for BOARDING_ALERT event."""
        event = Event(
            event_type=EventType.BOARDING_ALERT,
            payload={"flight_id": "FL123", "gate": "A1"},
            source_agent="flight_intelligence_agent",
            vip_id="test-vip-123",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        message = ws_manager._create_websocket_message(event)
        
        assert message["type"] == "flight_update"
        assert message["payload"]["event_type"] == "boarding_alert"
    
    def test_create_message_state_changed(self, ws_manager):
        """Test creating WebSocket message for STATE_CHANGED event."""
        event = Event(
            event_type=EventType.STATE_CHANGED,
            payload={"old_state": "arrived", "new_state": "buggy_pickup"},
            source_agent="master_orchestrator",
            vip_id="test-vip-123",
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        message = ws_manager._create_websocket_message(event)
        
        assert message["type"] == "vip_update"
        assert message["payload"]["event_type"] == "state_changed"


class TestWebSocketEventHandling:
    """Test Event Bus event handling and broadcasting."""
    
    @pytest.mark.asyncio
    async def test_handle_event_broadcasts_to_clients(self, ws_manager, sample_event):
        """Test that handling an event broadcasts it to all clients."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        
        await ws_manager.connect(ws1)
        await ws_manager.connect(ws2)
        
        await ws_manager.handle_event(sample_event)
        
        # Both clients should receive the message
        assert ws1.send_json.call_count == 1
        assert ws2.send_json.call_count == 1
        
        # Verify message structure
        call_args = ws1.send_json.call_args[0][0]
        assert call_args["type"] == "vip_update"
        assert call_args["payload"]["event_type"] == "vip_detected"
        assert call_args["payload"]["vip_id"] == "test-vip-123"
    
    @pytest.mark.asyncio
    async def test_handle_event_with_no_clients(self, ws_manager, sample_event):
        """Test handling event when no clients are connected."""
        # Should not raise an error
        await ws_manager.handle_event(sample_event)
    
    @pytest.mark.asyncio
    async def test_handle_multiple_event_types(self, ws_manager):
        """Test handling different event types."""
        ws = AsyncMock()
        await ws_manager.connect(ws)
        
        # Test different event types
        events = [
            Event(event_type=EventType.VIP_DETECTED, payload={}, source_agent="agent1", vip_id="vip1"),
            Event(event_type=EventType.ESCORT_ASSIGNED, payload={}, source_agent="agent2", vip_id="vip1"),
            Event(event_type=EventType.BUGGY_DISPATCHED, payload={}, source_agent="agent3", vip_id="vip1"),
            Event(event_type=EventType.LOUNGE_ENTRY, payload={}, source_agent="agent4", vip_id="vip1"),
            Event(event_type=EventType.FLIGHT_DELAY, payload={}, source_agent="agent5", vip_id="vip1"),
        ]
        
        for event in events:
            await ws_manager.handle_event(event)
        
        # Should have sent 5 messages
        assert ws.send_json.call_count == 5


class TestWebSocketCloseAll:
    """Test closing all WebSocket connections."""
    
    @pytest.mark.asyncio
    async def test_close_all_connections(self, ws_manager):
        """Test closing all WebSocket connections."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()
        
        await ws_manager.connect(ws1)
        await ws_manager.connect(ws2)
        await ws_manager.connect(ws3)
        
        assert ws_manager.get_connection_count() == 3
        
        await ws_manager.close_all()
        
        ws1.close.assert_called_once()
        ws2.close.assert_called_once()
        ws3.close.assert_called_once()
        assert ws_manager.get_connection_count() == 0
    
    @pytest.mark.asyncio
    async def test_close_all_with_failing_connection(self, ws_manager):
        """Test closing all connections when one fails."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws2.close = AsyncMock(side_effect=Exception("Close error"))
        ws3 = AsyncMock()
        
        await ws_manager.connect(ws1)
        await ws_manager.connect(ws2)
        await ws_manager.connect(ws3)
        
        # Should not raise an error
        await ws_manager.close_all()
        
        # All connections should be cleared
        assert ws_manager.get_connection_count() == 0
    
    @pytest.mark.asyncio
    async def test_close_all_with_no_connections(self, ws_manager):
        """Test closing all connections when none are connected."""
        # Should not raise an error
        await ws_manager.close_all()
        assert ws_manager.get_connection_count() == 0


class TestWebSocketMessageTypes:
    """Test that all required message types are supported."""
    
    def test_all_message_types_supported(self, ws_manager):
        """Test that all required WebSocket message types are supported."""
        required_message_types = [
            "vip_update",
            "escort_update",
            "buggy_update",
            "lounge_update",
            "flight_update"
        ]
        
        # Map event types to expected message types
        event_message_mapping = {
            EventType.VIP_DETECTED: "vip_update",
            EventType.STATE_CHANGED: "vip_update",
            EventType.ESCORT_ASSIGNED: "escort_update",
            EventType.BUGGY_DISPATCHED: "buggy_update",
            EventType.LOUNGE_RESERVED: "lounge_update",
            EventType.LOUNGE_ENTRY: "lounge_update",
            EventType.FLIGHT_DELAY: "flight_update",
            EventType.BOARDING_ALERT: "flight_update",
            EventType.BAGGAGE_PRIORITY_TAGGED: "vip_update",
        }
        
        # Test each event type produces the correct message type
        for event_type, expected_message_type in event_message_mapping.items():
            event = Event(
                event_type=event_type,
                payload={},
                source_agent="test_agent",
                vip_id="test-vip"
            )
            
            message = ws_manager._create_websocket_message(event)
            assert message["type"] == expected_message_type
            assert message["type"] in required_message_types
