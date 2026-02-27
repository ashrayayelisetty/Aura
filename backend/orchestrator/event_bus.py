"""
Event Bus for AURA-VIP Orchestration System.

This module implements the central event bus for inter-agent communication.
Validates Requirements 13.1, 13.2, 13.4, 13.5
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional
from uuid import uuid4

from backend.models.schemas import Event, EventType, ServiceLog
from backend.database.connection import SessionLocal
from backend.database.models import ServiceLogDB

logger = logging.getLogger(__name__)


class EventBus:
    """
    Central event bus for system-wide event communication.
    
    Responsibilities:
    - Maintain event subscription registry
    - Deliver events to subscribed agents
    - Log all events for audit trail
    - Handle event delivery failures with retry logic
    """
    
    def __init__(self):
        """Initialize the event bus with empty subscription registry."""
        # Dict mapping event types to list of handler functions
        self._subscriptions: Dict[EventType, List[Callable]] = defaultdict(list)
        self._event_history: List[Event] = []
        logger.info("Event Bus initialized")
    
    def subscribe(self, event_type: EventType, handler: Callable) -> None:
        """
        Register agent handler for specific event type.
        
        Args:
            event_type: The type of event to subscribe to
            handler: Async callable that will be invoked when event is published
        
        Validates: Requirement 13.1
        """
        if handler not in self._subscriptions[event_type]:
            self._subscriptions[event_type].append(handler)
            handler_name = getattr(handler, '__name__', repr(handler))
            logger.info(f"Subscribed handler {handler_name} to event type {event_type.value}")
    
    def unsubscribe(self, event_type: EventType, handler: Callable) -> None:
        """
        Unregister agent handler from specific event type.
        
        Args:
            event_type: The type of event to unsubscribe from
            handler: The handler to remove
        """
        if handler in self._subscriptions[event_type]:
            self._subscriptions[event_type].remove(handler)
            handler_name = getattr(handler, '__name__', repr(handler))
            logger.info(f"Unsubscribed handler {handler_name} from event type {event_type.value}")
    
    async def publish(self, event: Event) -> None:
        """
        Deliver event to all subscribed handlers.
        
        Args:
            event: The event to publish
        
        Validates: Requirement 13.2
        """
        # Log the event to database
        await self._log_event_to_db(event)
        
        # Add to in-memory history
        self._event_history.append(event)
        
        # Get event type (handle both enum and string)
        event_type = event.event_type if isinstance(event.event_type, EventType) else EventType(event.event_type)
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
        
        # Get all handlers for this event type
        handlers = self._subscriptions.get(event_type, [])
        
        if not handlers:
            logger.warning(f"No subscribers for event type {event_type_str}")
            return
        
        logger.info(f"Publishing event {event_type_str} to {len(handlers)} subscribers")
        
        # Deliver to all subscribers
        for handler in handlers:
            try:
                # Call handler asynchronously
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
                handler_name = getattr(handler, '__name__', repr(handler))
                logger.debug(f"Successfully delivered event to {handler_name}")
            except Exception as e:
                handler_name = getattr(handler, '__name__', repr(handler))
                logger.error(f"Error delivering event to {handler_name}: {e}", exc_info=True)
    
    async def publish_with_retry(
        self, 
        event: Event, 
        max_retries: int = 3,
        base_delay: float = 1.0
    ) -> None:
        """
        Publish event with retry logic for failed deliveries.
        
        Uses exponential backoff: delay = base_delay * (2 ** attempt)
        
        Args:
            event: The event to publish
            max_retries: Maximum number of retry attempts (default: 3)
            base_delay: Base delay in seconds for exponential backoff (default: 1.0)
        
        Validates: Requirement 13.5
        """
        # Log the event to database first
        await self._log_event_to_db(event)
        
        # Add to in-memory history
        self._event_history.append(event)
        
        # Get event type (handle both enum and string)
        event_type = event.event_type if isinstance(event.event_type, EventType) else EventType(event.event_type)
        event_type_str = event_type.value if isinstance(event_type, EventType) else event_type
        
        # Get all handlers for this event type
        handlers = self._subscriptions.get(event_type, [])
        
        if not handlers:
            logger.warning(f"No subscribers for event type {event_type_str}")
            return
        
        logger.info(f"Publishing event {event_type_str} with retry to {len(handlers)} subscribers")
        
        # Deliver to all subscribers with retry logic
        for handler in handlers:
            success = False
            last_error = None
            handler_name = getattr(handler, '__name__', repr(handler))
            
            for attempt in range(max_retries + 1):  # +1 for initial attempt
                try:
                    # Call handler asynchronously
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                    
                    logger.debug(f"Successfully delivered event to {handler_name} on attempt {attempt + 1}")
                    success = True
                    break
                    
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        # Calculate exponential backoff delay
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            f"Failed to deliver event to {handler_name} on attempt {attempt + 1}, "
                            f"retrying in {delay}s: {e}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Failed to deliver event to {handler_name} after {max_retries + 1} attempts: {e}",
                            exc_info=True
                        )
            
            if not success:
                # Log permanent failure
                logger.error(
                    f"Permanent failure delivering event {event_type_str} to {handler_name}: {last_error}"
                )
    
    async def _log_event_to_db(self, event: Event) -> None:
        """
        Log event to database service_logs table.
        
        Args:
            event: The event to log
        
        Validates: Requirement 13.4
        """
        try:
            db = SessionLocal()
            try:
                # Get event type string (handle both enum and string)
                event_type_str = event.event_type.value if isinstance(event.event_type, EventType) else event.event_type
                
                # Create service log entry
                service_log = ServiceLogDB(
                    id=str(uuid4()),
                    vip_id=event.vip_id or "system",  # Use "system" for non-VIP events
                    event_type=event_type_str,
                    event_data=event.payload,
                    timestamp=event.timestamp,
                    agent_source=event.source_agent
                )
                
                db.add(service_log)
                db.commit()
                logger.debug(f"Logged event {event_type_str} to database")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to log event to database: {e}", exc_info=True)
    
    def get_event_history(self, vip_id: Optional[str] = None) -> List[Event]:
        """
        Retrieve event history, optionally filtered by VIP ID.
        
        Args:
            vip_id: Optional VIP ID to filter events
        
        Returns:
            List of events, filtered by VIP ID if provided
        """
        if vip_id:
            return [e for e in self._event_history if e.vip_id == vip_id]
        return self._event_history.copy()
    
    def get_subscription_count(self, event_type: EventType) -> int:
        """
        Get the number of subscribers for a specific event type.
        
        Args:
            event_type: The event type to check
        
        Returns:
            Number of subscribed handlers
        """
        return len(self._subscriptions.get(event_type, []))
    
    def clear_history(self) -> None:
        """Clear in-memory event history (useful for testing)."""
        self._event_history.clear()
        logger.info("Event history cleared")
