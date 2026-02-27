"""
Baggage Agent for AURA-VIP Orchestration System.

This module implements priority baggage handling for VIPs.
Validates Requirements 7.1, 7.2, 7.3, 7.4, 7.5
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from backend.models.schemas import Event, EventType, VIPState
from backend.orchestrator.event_bus import EventBus
from backend.database.connection import SessionLocal
from backend.database.models import VIPProfileDB

logger = logging.getLogger(__name__)


class BaggageAgent:
    """
    Baggage Agent responsible for priority baggage handling.
    
    Responsibilities:
    - Generate priority baggage tags for VIPs
    - Simulate priority baggage routing
    - Track baggage loading status
    - Adjust priority for flight delays
    """
    
    def __init__(self, event_bus: EventBus):
        """
        Initialize the Baggage Agent.
        
        Args:
            event_bus: The event bus for publishing and subscribing to events
        """
        self.event_bus = event_bus
        
        # Track baggage status for each VIP
        # Status values: "tagged", "routing", "loaded"
        self._baggage_status: Dict[str, str] = {}
        
        # Track baggage priority (higher number = higher priority)
        self._baggage_priority: Dict[str, int] = {}
        
        # Subscribe to relevant events
        self.event_bus.subscribe(EventType.STATE_CHANGED, self.handle_state_changed)
        self.event_bus.subscribe(EventType.FLIGHT_DELAY, self.handle_flight_delay)
        
        logger.info("Baggage Agent initialized and subscribed to events")
    
    async def handle_state_changed(self, event: Event) -> None:
        """
        Handle STATE_CHANGED event to generate priority tags when VIP checks in.
        
        Args:
            event: The STATE_CHANGED event
        
        Validates: Requirements 7.1, 7.2
        """
        vip_id = event.vip_id or event.payload.get("vip_id")
        new_state = event.payload.get("new_state")
        
        if not vip_id or not new_state:
            logger.error("STATE_CHANGED event missing vip_id or new_state")
            return
        
        # Generate priority tag when VIP transitions to CHECKED_IN
        if new_state == VIPState.CHECKED_IN.value:
            logger.info(f"VIP {vip_id} checked in, generating priority baggage tag")
            await self.generate_priority_tag(vip_id)
    
    async def handle_flight_delay(self, event: Event) -> None:
        """
        Handle FLIGHT_DELAY event by adjusting baggage priority.
        
        Args:
            event: The FLIGHT_DELAY event
        
        Validates: Requirement 7.5
        """
        vip_id = event.vip_id or event.payload.get("vip_id")
        flight_id = event.payload.get("flight_id")
        delay_minutes = event.payload.get("delay_minutes", 0)
        
        if not vip_id and not flight_id:
            logger.error("FLIGHT_DELAY event missing vip_id or flight_id")
            return
        
        # If flight_id is provided, find all VIPs on that flight
        if flight_id:
            vip_ids = await self._get_vips_on_flight(flight_id)
            for vid in vip_ids:
                await self.adjust_priority_for_delay(vid, delay_minutes)
        elif vip_id:
            await self.adjust_priority_for_delay(vip_id, delay_minutes)
    
    async def generate_priority_tag(self, vip_id: str) -> None:
        """
        Generate priority baggage tag for VIP in CHECKED_IN state.
        
        Args:
            vip_id: The ID of the VIP
        
        Validates: Requirements 7.1, 7.2
        """
        try:
            # Get VIP profile to retrieve flight information
            db = SessionLocal()
            try:
                vip = db.query(VIPProfileDB).filter(VIPProfileDB.id == vip_id).first()
                
                if not vip:
                    logger.error(f"VIP {vip_id} not found")
                    return
                
                flight_id = vip.flight_id
                
            finally:
                db.close()
            
            # Generate priority tag (in real system, this would interface with baggage system)
            tag_id = f"VIP-{vip_id[:8]}-{flight_id}"
            
            # Set initial priority (VIPs get priority 10, regular passengers would be 1)
            self._baggage_priority[vip_id] = 10
            
            # Update status
            self._baggage_status[vip_id] = "tagged"
            
            logger.info(f"Generated priority baggage tag {tag_id} for VIP {vip_id}")
            
            # Emit BAGGAGE_PRIORITY_TAGGED event
            event = Event(
                event_type=EventType.BAGGAGE_PRIORITY_TAGGED,
                payload={
                    "vip_id": vip_id,
                    "tag_id": tag_id,
                    "flight_id": flight_id,
                    "priority": self._baggage_priority[vip_id],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                source_agent="baggage_agent",
                vip_id=vip_id
            )
            
            await self.event_bus.publish(event)
            
            logger.info(f"Emitted BAGGAGE_PRIORITY_TAGGED event for VIP {vip_id}")
            
            # Start baggage routing simulation
            asyncio.create_task(self.simulate_baggage_routing(vip_id, flight_id))
            
        except Exception as e:
            logger.error(f"Failed to generate priority tag: {e}", exc_info=True)
    
    async def simulate_baggage_routing(self, vip_id: str, flight_id: str) -> None:
        """
        Simulate priority baggage routing through the baggage handling system.
        
        Args:
            vip_id: The ID of the VIP
            flight_id: The flight ID
        
        Validates: Requirement 7.3
        """
        try:
            logger.info(f"Starting baggage routing simulation for VIP {vip_id}")
            
            # Update status to routing
            self._baggage_status[vip_id] = "routing"
            
            # Simulate baggage handling time
            # Priority baggage gets expedited handling (3 minutes vs 10 minutes for regular)
            routing_time_seconds = 3 * 60
            
            logger.info(f"Simulating {routing_time_seconds / 60} minute routing for VIP {vip_id} baggage")
            await asyncio.sleep(routing_time_seconds)
            
            # Update status to loaded
            self._baggage_status[vip_id] = "loaded"
            
            # Log completion time
            completion_time = datetime.now(timezone.utc)
            logger.info(f"Baggage for VIP {vip_id} reached aircraft at {completion_time.isoformat()}")
            
            # Log to database via service log
            event = Event(
                event_type=EventType.STATE_CHANGED,
                payload={
                    "vip_id": vip_id,
                    "baggage_status": "loaded",
                    "completion_time": completion_time.isoformat(),
                    "flight_id": flight_id,
                    "message": "Baggage loaded onto aircraft"
                },
                source_agent="baggage_agent",
                vip_id=vip_id
            )
            
            await self.event_bus.publish(event)
            
            logger.info(f"Baggage routing completed for VIP {vip_id}")
            
        except Exception as e:
            logger.error(f"Failed to simulate baggage routing: {e}", exc_info=True)
    
    async def track_loading_status(self, vip_id: str) -> str:
        """
        Get current baggage loading status for a VIP.
        
        Args:
            vip_id: The ID of the VIP
        
        Returns:
            Current baggage status ("not_tagged", "tagged", "routing", "loaded")
        
        Validates: Requirement 7.3
        """
        return self._baggage_status.get(vip_id, "not_tagged")
    
    async def adjust_priority_for_delay(self, vip_id: str, delay_minutes: int) -> None:
        """
        Adjust baggage loading priority when flight is delayed.
        
        Args:
            vip_id: The ID of the VIP
            delay_minutes: Number of minutes the flight is delayed
        
        Validates: Requirement 7.5
        """
        try:
            # Check if baggage is already tagged
            if vip_id not in self._baggage_priority:
                logger.warning(f"No baggage priority found for VIP {vip_id}")
                return
            
            current_status = self._baggage_status.get(vip_id, "not_tagged")
            
            # Only adjust priority if baggage hasn't been loaded yet
            if current_status == "loaded":
                logger.info(f"Baggage for VIP {vip_id} already loaded, no priority adjustment needed")
                return
            
            # Adjust priority based on delay
            # Longer delays = lower priority (more time available)
            # Shorter delays = maintain high priority
            old_priority = self._baggage_priority[vip_id]
            
            if delay_minutes > 60:
                # Significant delay, reduce priority slightly
                self._baggage_priority[vip_id] = max(5, old_priority - 3)
            elif delay_minutes > 30:
                # Moderate delay, reduce priority slightly
                self._baggage_priority[vip_id] = max(7, old_priority - 2)
            else:
                # Short delay, maintain high priority
                self._baggage_priority[vip_id] = max(8, old_priority - 1)
            
            new_priority = self._baggage_priority[vip_id]
            
            logger.info(
                f"Adjusted baggage priority for VIP {vip_id} from {old_priority} to {new_priority} "
                f"due to {delay_minutes} minute flight delay"
            )
            
        except Exception as e:
            logger.error(f"Failed to adjust baggage priority: {e}", exc_info=True)
    
    async def _get_vips_on_flight(self, flight_id: str) -> list:
        """
        Get all VIP IDs on a specific flight.
        
        Args:
            flight_id: The flight ID
        
        Returns:
            List of VIP IDs on the flight
        """
        try:
            db = SessionLocal()
            try:
                vips = db.query(VIPProfileDB).filter(
                    VIPProfileDB.flight_id == flight_id
                ).all()
                
                return [vip.id for vip in vips]
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to get VIPs on flight: {e}", exc_info=True)
            return []
