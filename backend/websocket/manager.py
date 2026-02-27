"""
WebSocket Manager for AURA-VIP Orchestration System.

This module implements the WebSocket manager for real-time communication
between backend and frontend clients.
Validates Requirements 16.1, 16.2, 16.3, 16.5, 8.2
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Set
from fastapi import WebSocket

from backend.models.schemas import Event, EventType

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    WebSocket manager for real-time client communication.
    
    Responsibilities:
    - Manage WebSocket connections from frontend clients
    - Push real-time updates to connected clients
    - Handle connection lifecycle (connect, disconnect, reconnect)
    - Broadcast events to all connected clients
    - Subscribe to Event Bus and push events to WebSocket clients
    """
    
    def __init__(self):
        """Initialize the WebSocket manager with empty connection pool."""
        # Set of active WebSocket connections
        self._connections: Set[WebSocket] = set()
        logger.info("WebSocket Manager initialized")
    
    async def connect(self, websocket: WebSocket) -> None:
        """
        Accept new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection to accept
        
        Validates: Requirement 16.1
        """
        await websocket.accept()
        self._connections.add(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(self._connections)}")
    
    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Handle client disconnection.
        
        Args:
            websocket: The WebSocket connection to remove
        """
        if websocket in self._connections:
            self._connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total connections: {len(self._connections)}")
    
    async def broadcast(self, message: dict) -> None:
        """
        Send message to all connected clients.
        
        Args:
            message: The message dictionary to broadcast
        
        Validates: Requirement 16.2, 16.3
        """
        if not self._connections:
            logger.debug("No WebSocket clients connected, skipping broadcast")
            return
        
        logger.debug(f"Broadcasting message to {len(self._connections)} clients: {message.get('type')}")
        
        # Track disconnected clients
        disconnected = set()
        
        # Send to all connected clients
        for websocket in self._connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to client: {e}")
                disconnected.add(websocket)
        
        # Remove disconnected clients
        for websocket in disconnected:
            await self.disconnect(websocket)
    
    async def send_to_client(self, websocket: WebSocket, message: dict) -> None:
        """
        Send message to specific client.
        
        Args:
            websocket: The target WebSocket connection
            message: The message dictionary to send
        """
        try:
            await websocket.send_json(message)
            logger.debug(f"Sent message to client: {message.get('type')}")
        except Exception as e:
            logger.error(f"Error sending message to specific client: {e}")
            await self.disconnect(websocket)
    
    def _create_websocket_message(self, event: Event) -> dict:
        """
        Create WebSocket message from Event Bus event.
        
        Args:
            event: The Event Bus event
        
        Returns:
            WebSocket message dictionary with type, payload, timestamp
        
        Validates: Requirement 16.3
        """
        # Map event types to WebSocket message types
        event_to_message_type = {
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
        
        # Get event type (handle both enum and string)
        event_type = event.event_type if isinstance(event.event_type, EventType) else EventType(event.event_type)
        
        # Determine message type
        message_type = event_to_message_type.get(event_type, "vip_update")
        
        # Create message with required format: {type, payload, timestamp}
        message = {
            "type": message_type,
            "payload": {
                "event_type": event_type.value if isinstance(event_type, EventType) else event_type,
                "vip_id": event.vip_id,
                "source_agent": event.source_agent,
                **event.payload
            },
            "timestamp": event.timestamp.isoformat()
        }
        
        return message
    
    async def handle_event(self, event: Event) -> None:
        """
        Handle Event Bus event and push to WebSocket clients.
        
        This method is subscribed to all Event Bus events and pushes
        updates to connected WebSocket clients within 500ms.
        
        Args:
            event: The Event Bus event to handle
        
        Validates: Requirement 16.2, 16.5, 8.2
        """
        # Create WebSocket message from event
        message = self._create_websocket_message(event)
        
        # Broadcast to all connected clients
        await self.broadcast(message)
    
    def get_connection_count(self) -> int:
        """
        Get the number of active WebSocket connections.
        
        Returns:
            Number of active connections
        """
        return len(self._connections)
    
    async def close_all(self) -> None:
        """Close all WebSocket connections (useful for shutdown)."""
        logger.info(f"Closing all {len(self._connections)} WebSocket connections")
        
        for websocket in list(self._connections):
            try:
                await websocket.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")
        
        self._connections.clear()
        logger.info("All WebSocket connections closed")
