"""
Transport Agent for AURA-VIP Orchestration System.

This module implements buggy allocation, dispatch, and battery management.
Validates Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 11.2, 11.3
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from backend.models.schemas import Event, EventType, BuggyStatus, VIPState
from backend.orchestrator.event_bus import EventBus
from backend.database.connection import SessionLocal
from backend.database.models import BuggyDB

logger = logging.getLogger(__name__)


class TransportAgent:
    """
    Transport Agent responsible for buggy allocation and dispatch.
    
    Responsibilities:
    - Manage buggy fleet availability
    - Allocate buggies to VIPs
    - Simulate buggy dispatch and battery depletion
    - Track buggy locations and status
    """
    
    def __init__(self, event_bus: EventBus):
        """
        Initialize the Transport Agent.
        
        Args:
            event_bus: The event bus for publishing and subscribing to events
        """
        self.event_bus = event_bus
        
        # Subscribe to relevant events
        self.event_bus.subscribe(EventType.VIP_DETECTED, self.handle_vip_detected)
        self.event_bus.subscribe(EventType.STATE_CHANGED, self.handle_state_changed)
        self.event_bus.subscribe(EventType.BOARDING_ALERT, self.handle_boarding_alert)
        
        logger.info("Transport Agent initialized and subscribed to events")

    async def handle_vip_detected(self, event: Event) -> None:
        """
        Handle VIP_DETECTED event by allocating a buggy.
        
        Args:
            event: The VIP_DETECTED event
        
        Validates: Requirements 4.1, 4.2
        """
        vip_id = event.vip_id or event.payload.get("vip_id")
        
        if not vip_id:
            logger.error("VIP_DETECTED event missing vip_id")
            return
        
        logger.info(f"Handling VIP detected for VIP ID: {vip_id}")
        
        # Allocate a buggy to the VIP
        await self.allocate_buggy_to_vip(vip_id)
    
    async def handle_state_changed(self, event: Event) -> None:
        """
        Handle STATE_CHANGED event to dispatch buggy or release it.
        
        Args:
            event: The STATE_CHANGED event
        
        Validates: Requirements 4.3, 4.5
        """
        vip_id = event.vip_id or event.payload.get("vip_id")
        new_state = event.payload.get("new_state")
        
        if not vip_id or not new_state:
            logger.error("STATE_CHANGED event missing vip_id or new_state")
            return
        
        # Dispatch buggy to lounge when VIP clears security
        if new_state == VIPState.SECURITY_CLEARED.value:
            logger.info(f"VIP {vip_id} cleared security, dispatching buggy to lounge")
            await self.dispatch_buggy_to_lounge(vip_id)
        
        # Release buggy when VIP boards
        elif new_state == VIPState.BOARDED.value:
            logger.info(f"VIP {vip_id} boarded, releasing buggy")
            await self.release_buggy_by_vip(vip_id)

    async def handle_boarding_alert(self, event: Event) -> None:
        """
        Handle BOARDING_ALERT event by dispatching buggy to gate.
        
        Args:
            event: The BOARDING_ALERT event
        
        Validates: Requirement 4.4
        """
        vip_id = event.vip_id or event.payload.get("vip_id")
        
        if not vip_id:
            logger.error("BOARDING_ALERT event missing vip_id")
            return
        
        logger.info(f"Boarding alert for VIP {vip_id}, dispatching buggy to gate")
        await self.dispatch_buggy_to_gate(vip_id)
    
    async def find_available_buggy(self) -> Optional[str]:
        """
        Find buggy with battery level above 20%.
        
        Returns:
            Buggy ID if available, None otherwise
        
        Validates: Requirement 4.1
        """
        try:
            db = SessionLocal()
            try:
                # Query for buggies with status=available and battery > 20%
                buggy = db.query(BuggyDB).filter(
                    BuggyDB.status == BuggyStatus.AVAILABLE.value,
                    BuggyDB.battery_level > 20
                ).first()
                
                if buggy:
                    logger.info(f"Found available buggy: ID {buggy.id} with {buggy.battery_level}% battery")
                    return buggy.id
                else:
                    logger.warning("No available buggies found with battery > 20%")
                    return None
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to find available buggy: {e}", exc_info=True)
            return None

    async def dispatch_buggy(self, buggy_id: str, vip_id: str, destination: str) -> None:
        """
        Assign buggy to VIP and update status.
        
        Args:
            buggy_id: The ID of the buggy to dispatch
            vip_id: The ID of the VIP
            destination: The destination ("lounge" or "gate")
        
        Validates: Requirement 4.2
        """
        try:
            db = SessionLocal()
            try:
                # Get the buggy
                buggy = db.query(BuggyDB).filter(BuggyDB.id == buggy_id).first()
                
                if not buggy:
                    logger.error(f"Buggy {buggy_id} not found")
                    return
                
                # Update buggy status and assignment
                buggy.status = BuggyStatus.ASSIGNED.value
                buggy.assigned_vip_id = vip_id
                buggy.current_location = "en_route_pickup" if destination == "lounge" else "en_route_destination"
                
                db.commit()
                
                logger.info(f"Dispatched buggy {buggy_id} to VIP {vip_id} for {destination}")
                
                # Emit BUGGY_DISPATCHED event
                event = Event(
                    event_type=EventType.BUGGY_DISPATCHED,
                    payload={
                        "buggy_id": buggy_id,
                        "vip_id": vip_id,
                        "destination": destination,
                        "battery_level": buggy.battery_level,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    },
                    source_agent="transport_agent",
                    vip_id=vip_id
                )
                
                await self.event_bus.publish(event)
                
                logger.info(f"Emitted BUGGY_DISPATCHED event for VIP {vip_id}")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to dispatch buggy: {e}", exc_info=True)

    async def simulate_trip(self, buggy_id: str, duration_minutes: int) -> None:
        """
        Simulate buggy trip with battery depletion (5% per trip).
        
        Args:
            buggy_id: The ID of the buggy
            duration_minutes: Trip duration in minutes
        
        Validates: Requirements 11.2, 11.3
        """
        try:
            # Simulate trip duration - use fast demo speed (1 second per "minute")
            logger.info(f"Simulating {duration_minutes} minute trip for buggy {buggy_id}")
            await asyncio.sleep(duration_minutes)  # Fast demo: 1 second per minute
            
            db = SessionLocal()
            try:
                # Get the buggy
                buggy = db.query(BuggyDB).filter(BuggyDB.id == buggy_id).first()
                
                if not buggy:
                    logger.error(f"Buggy {buggy_id} not found")
                    return
                
                # Deplete battery by 5%
                old_battery = buggy.battery_level
                buggy.battery_level = max(0, buggy.battery_level - 5)
                
                logger.info(f"Buggy {buggy_id} battery depleted from {old_battery}% to {buggy.battery_level}%")
                
                # Update location to idle after trip
                buggy.current_location = "idle"
                
                # If battery falls below 20%, mark as unavailable
                if buggy.battery_level <= 20:
                    logger.warning(f"Buggy {buggy_id} battery at {buggy.battery_level}%, marking as unavailable")
                    buggy.status = BuggyStatus.CHARGING.value
                    buggy.assigned_vip_id = None
                
                db.commit()
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to simulate trip: {e}", exc_info=True)

    async def release_buggy(self, buggy_id: str) -> None:
        """
        Mark buggy as available if battery level is above 20%.
        
        Args:
            buggy_id: The ID of the buggy to release
        
        Validates: Requirement 4.5
        """
        try:
            db = SessionLocal()
            try:
                # Get the buggy
                buggy = db.query(BuggyDB).filter(BuggyDB.id == buggy_id).first()
                
                if not buggy:
                    logger.error(f"Buggy {buggy_id} not found")
                    return
                
                # Only mark as available if battery > 20%
                if buggy.battery_level > 20:
                    buggy.status = BuggyStatus.AVAILABLE.value
                    buggy.assigned_vip_id = None
                    buggy.current_location = "idle"
                    logger.info(f"Released buggy {buggy_id} (battery: {buggy.battery_level}%)")
                else:
                    buggy.status = BuggyStatus.CHARGING.value
                    buggy.assigned_vip_id = None
                    buggy.current_location = "idle"
                    logger.warning(f"Buggy {buggy_id} battery at {buggy.battery_level}%, marked as charging")
                
                db.commit()
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to release buggy: {e}", exc_info=True)
    
    async def release_buggy_by_vip(self, vip_id: str) -> None:
        """
        Release buggy assigned to a specific VIP.
        
        Args:
            vip_id: The ID of the VIP whose buggy should be released
        
        Validates: Requirement 4.5
        """
        try:
            db = SessionLocal()
            try:
                # Find buggy assigned to this VIP
                buggy = db.query(BuggyDB).filter(
                    BuggyDB.assigned_vip_id == vip_id
                ).first()
                
                if buggy:
                    logger.info(f"Found buggy {buggy.id} assigned to VIP {vip_id}")
                    await self.release_buggy(buggy.id)
                else:
                    logger.warning(f"No buggy found assigned to VIP {vip_id}")
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to release buggy by VIP: {e}", exc_info=True)

    async def allocate_buggy_to_vip(self, vip_id: str) -> None:
        """
        Allocate a buggy to a VIP when they arrive.
        
        Args:
            vip_id: The ID of the VIP requesting a buggy
        
        Validates: Requirements 4.1, 4.2
        """
        # Find an available buggy
        buggy_id = await self.find_available_buggy()
        
        if buggy_id:
            # Dispatch the buggy for initial pickup
            await self.dispatch_buggy(buggy_id, vip_id, "arrival")
        else:
            logger.warning(f"No buggies available for VIP {vip_id}")
    
    async def dispatch_buggy_to_lounge(self, vip_id: str) -> None:
        """
        Dispatch buggy to transport VIP to lounge.
        
        Args:
            vip_id: The ID of the VIP
        
        Validates: Requirement 4.3
        """
        try:
            db = SessionLocal()
            try:
                # Find buggy assigned to this VIP
                buggy = db.query(BuggyDB).filter(
                    BuggyDB.assigned_vip_id == vip_id
                ).first()
                
                if not buggy:
                    logger.error(f"No buggy assigned to VIP {vip_id}")
                    return
                
                buggy_id = buggy.id
                
            finally:
                db.close()
            
            # Update buggy location
            await self._update_buggy_location(buggy_id, "en_route_destination")
            
            # Simulate trip to lounge (5 minutes)
            await self.simulate_trip(buggy_id, 5)
            
            logger.info(f"Buggy {buggy_id} completed trip to lounge for VIP {vip_id}")
            
        except Exception as e:
            logger.error(f"Failed to dispatch buggy to lounge: {e}", exc_info=True)

    async def dispatch_buggy_to_gate(self, vip_id: str) -> None:
        """
        Dispatch buggy to transport VIP from lounge to gate.
        
        Args:
            vip_id: The ID of the VIP
        
        Validates: Requirement 4.4
        """
        try:
            db = SessionLocal()
            try:
                # Find buggy assigned to this VIP
                buggy = db.query(BuggyDB).filter(
                    BuggyDB.assigned_vip_id == vip_id
                ).first()
                
                if not buggy:
                    logger.error(f"No buggy assigned to VIP {vip_id}")
                    return
                
                buggy_id = buggy.id
                
            finally:
                db.close()
            
            # Update buggy location
            await self._update_buggy_location(buggy_id, "en_route_destination")
            
            # Simulate trip to gate (7 minutes)
            await self.simulate_trip(buggy_id, 7)
            
            logger.info(f"Buggy {buggy_id} completed trip to gate for VIP {vip_id}")
            
        except Exception as e:
            logger.error(f"Failed to dispatch buggy to gate: {e}", exc_info=True)
    
    async def _update_buggy_location(self, buggy_id: str, location: str) -> None:
        """
        Update buggy location in database.
        
        Args:
            buggy_id: The ID of the buggy
            location: The new location
        """
        try:
            db = SessionLocal()
            try:
                buggy = db.query(BuggyDB).filter(BuggyDB.id == buggy_id).first()
                
                if buggy:
                    buggy.current_location = location
                    db.commit()
                    logger.debug(f"Updated buggy {buggy_id} location to {location}")
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to update buggy location: {e}", exc_info=True)
