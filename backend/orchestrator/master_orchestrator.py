"""
Master Orchestrator for AURA-VIP Orchestration System.

This module implements the central workflow lifecycle controller that manages
VIP state transitions and coordinates agent activities through event emission.

Validates Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 6.4, 15.4
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from backend.models.schemas import Event, EventType, VIPState
from backend.orchestrator.event_bus import EventBus
from backend.database.connection import SessionLocal
from backend.database.models import VIPProfileDB, EscortDB, BuggyDB, LoungeReservationDB

logger = logging.getLogger(__name__)


class MasterOrchestrator:
    """
    Central workflow lifecycle controller managing state transitions and event triggers.
    
    Responsibilities:
    - Manage VIP workflow state machine
    - Enforce state transition rules
    - Coordinate agent activities through event emission
    - Handle workflow recovery on system restart
    """
    
    # Define valid state transitions
    VALID_TRANSITIONS = {
        VIPState.PREPARED: [VIPState.ARRIVED],
        VIPState.ARRIVED: [VIPState.BUGGY_PICKUP],
        VIPState.BUGGY_PICKUP: [VIPState.CHECKED_IN],
        VIPState.CHECKED_IN: [VIPState.SECURITY_CLEARED],
        VIPState.SECURITY_CLEARED: [VIPState.LOUNGE_ENTRY],
        VIPState.LOUNGE_ENTRY: [VIPState.BUGGY_TO_GATE],
        VIPState.BUGGY_TO_GATE: [VIPState.BOARDED],
        VIPState.BOARDED: [VIPState.COMPLETED],
        VIPState.COMPLETED: []  # Terminal state
    }
    
    def __init__(self, event_bus: EventBus):
        """
        Initialize the Master Orchestrator.
        
        Args:
            event_bus: The event bus for inter-agent communication
        """
        self.event_bus = event_bus
        self._active_workflows: Dict[str, VIPState] = {}
        
        # Subscribe to relevant events
        self.event_bus.subscribe(EventType.VIP_DETECTED, self.handle_vip_detected)
        self.event_bus.subscribe(EventType.FLIGHT_DELAY, self.handle_flight_delay)
        self.event_bus.subscribe(EventType.BOARDING_ALERT, self.handle_boarding_alert)
        
        logger.info("Master Orchestrator initialized")
    
    async def handle_vip_detected(self, event: Event) -> None:
        """
        Handle VIP_DETECTED event and transition VIP from PREPARED to ARRIVED state.
        
        Args:
            event: VIP_DETECTED event containing vip_id and confidence
        
        Validates: Requirement 2.1
        """
        vip_id = event.vip_id
        confidence = event.payload.get("confidence", 0.0)
        
        logger.info(f"VIP detected: {vip_id} with confidence {confidence}")
        
        # Transition VIP to ARRIVED state
        success = await self.transition_state(vip_id, VIPState.ARRIVED)
        
        if success:
            logger.info(f"VIP {vip_id} successfully transitioned to ARRIVED state")
        else:
            logger.error(f"Failed to transition VIP {vip_id} to ARRIVED state")
    
    async def transition_state(self, vip_id: str, new_state: VIPState) -> bool:
        """
        Validate and execute state transition for a VIP.
        
        Args:
            vip_id: The VIP identifier
            new_state: The target state to transition to
        
        Returns:
            True if transition was successful, False otherwise
        
        Validates: Requirements 2.2, 2.3, 2.4
        """
        db = SessionLocal()
        try:
            # Get current VIP state from database
            vip = db.query(VIPProfileDB).filter(VIPProfileDB.id == vip_id).first()
            
            if not vip:
                logger.error(f"VIP {vip_id} not found in database")
                return False
            
            current_state = VIPState(vip.current_state)
            
            # Validate transition
            if not self._is_valid_transition(current_state, new_state):
                logger.error(
                    f"Invalid state transition for VIP {vip_id}: "
                    f"{current_state.value} -> {new_state.value}"
                )
                return False
            
            # Update VIP state in database
            vip.current_state = new_state.value
            vip.updated_at = datetime.now(timezone.utc)
            db.commit()
            
            # Update in-memory tracking
            self._active_workflows[vip_id] = new_state
            
            logger.info(
                f"VIP {vip_id} transitioned: {current_state.value} -> {new_state.value}"
            )
            
            # Emit STATE_CHANGED event
            await self._emit_state_changed(vip_id, current_state, new_state)
            
            # Handle workflow completion
            if new_state == VIPState.COMPLETED:
                await self._release_resources(vip_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error transitioning VIP {vip_id} to {new_state.value}: {e}", exc_info=True)
            db.rollback()
            return False
        finally:
            db.close()
    
    def _is_valid_transition(self, current_state: VIPState, new_state: VIPState) -> bool:
        """
        Check if a state transition is valid according to the state machine rules.
        
        Args:
            current_state: The current VIP state
            new_state: The target state
        
        Returns:
            True if transition is valid, False otherwise
        
        Validates: Requirement 2.3
        """
        valid_next_states = self.VALID_TRANSITIONS.get(current_state, [])
        return new_state in valid_next_states
    
    async def _emit_state_changed(
        self, 
        vip_id: str, 
        previous_state: VIPState, 
        new_state: VIPState
    ) -> None:
        """
        Emit STATE_CHANGED event after successful transition.
        
        Args:
            vip_id: The VIP identifier
            previous_state: The previous state
            new_state: The new state
        
        Validates: Requirement 2.2
        """
        event = Event(
            event_type=EventType.STATE_CHANGED,
            payload={
                "vip_id": vip_id,
                "previous_state": previous_state.value,
                "new_state": new_state.value
            },
            source_agent="master_orchestrator",
            vip_id=vip_id
        )
        
        await self.event_bus.publish(event)
        logger.debug(f"Emitted STATE_CHANGED event for VIP {vip_id}")
    
    async def _release_resources(self, vip_id: str) -> None:
        """
        Release all assigned resources when VIP reaches COMPLETED state.
        
        Args:
            vip_id: The VIP identifier
        
        Validates: Requirement 2.5
        """
        db = SessionLocal()
        try:
            # Release escort
            escort = db.query(EscortDB).filter(EscortDB.assigned_vip_id == vip_id).first()
            if escort:
                escort.assigned_vip_id = None
                escort.status = "available"
                logger.info(f"Released escort {escort.id} for VIP {vip_id}")
            
            # Release buggy
            buggy = db.query(BuggyDB).filter(BuggyDB.assigned_vip_id == vip_id).first()
            if buggy:
                buggy.assigned_vip_id = None
                buggy.status = "available"
                buggy.current_location = "idle"
                logger.info(f"Released buggy {buggy.id} for VIP {vip_id}")
            
            # Release lounge reservation
            reservation = db.query(LoungeReservationDB).filter(
                LoungeReservationDB.vip_id == vip_id,
                LoungeReservationDB.status.in_(["reserved", "active"])
            ).first()
            if reservation:
                reservation.status = "completed"
                reservation.exit_time = datetime.now(timezone.utc)
                logger.info(f"Released lounge reservation {reservation.id} for VIP {vip_id}")
            
            db.commit()
            
            # Remove from active workflows
            if vip_id in self._active_workflows:
                del self._active_workflows[vip_id]
            
            logger.info(f"All resources released for VIP {vip_id}")
            
        except Exception as e:
            logger.error(f"Error releasing resources for VIP {vip_id}: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
    
    async def handle_flight_delay(self, event: Event) -> None:
        """
        Handle FLIGHT_DELAY event to extend lounge time and reschedule buggy.
        
        Args:
            event: FLIGHT_DELAY event containing flight_id and new_departure_time
        
        Validates: Requirement 6.4
        """
        flight_id = event.payload.get("flight_id")
        new_departure_str = event.payload.get("new_departure_time")
        delay_minutes = event.payload.get("delay_minutes", 0)
        
        logger.info(f"Flight delay detected for flight {flight_id}: {delay_minutes} minutes")
        
        db = SessionLocal()
        try:
            # Find all VIPs on this flight
            vips = db.query(VIPProfileDB).filter(VIPProfileDB.flight_id == flight_id).all()
            
            for vip in vips:
                # Only adjust if VIP is in lounge or earlier states
                current_state = VIPState(vip.current_state)
                if current_state in [VIPState.LOUNGE_ENTRY, VIPState.SECURITY_CLEARED]:
                    # Extend lounge reservation
                    reservation = db.query(LoungeReservationDB).filter(
                        LoungeReservationDB.vip_id == vip.id,
                        LoungeReservationDB.status.in_(["reserved", "active"])
                    ).first()
                    
                    if reservation:
                        reservation.duration_minutes += delay_minutes
                        logger.info(
                            f"Extended lounge reservation for VIP {vip.id} by {delay_minutes} minutes"
                        )
            
            db.commit()
            logger.info(f"Flight delay adjustments completed for flight {flight_id}")
            
        except Exception as e:
            logger.error(f"Error handling flight delay for flight {flight_id}: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
    
    async def handle_boarding_alert(self, event: Event) -> None:
        """
        Handle BOARDING_ALERT event to transition VIPs to BUGGY_TO_GATE state.
        
        Args:
            event: BOARDING_ALERT event containing flight_id and vip_ids
        
        Validates: Requirement 6.5
        """
        flight_id = event.payload.get("flight_id")
        vip_ids = event.payload.get("vip_ids", [])
        
        logger.info(f"Boarding alert for flight {flight_id}, transitioning {len(vip_ids)} VIPs")
        
        for vip_id in vip_ids:
            # Check if VIP is in LOUNGE_ENTRY state
            db = SessionLocal()
            try:
                vip = db.query(VIPProfileDB).filter(VIPProfileDB.id == vip_id).first()
                if vip and vip.current_state == VIPState.LOUNGE_ENTRY.value:
                    await self.transition_state(vip_id, VIPState.BUGGY_TO_GATE)
            finally:
                db.close()
    
    async def recover_workflows(self) -> None:
        """
        Restore active workflows from database on startup.
        
        Loads all VIPs that are not in COMPLETED state and adds them to
        the active workflows tracking.
        
        Validates: Requirement 15.4
        """
        db = SessionLocal()
        try:
            # Query all VIPs not in COMPLETED state
            active_vips = db.query(VIPProfileDB).filter(
                VIPProfileDB.current_state != VIPState.COMPLETED.value
            ).all()
            
            for vip in active_vips:
                vip_state = VIPState(vip.current_state)
                self._active_workflows[vip.id] = vip_state
                logger.info(f"Recovered workflow for VIP {vip.id} in state {vip_state.value}")
            
            logger.info(f"Recovered {len(active_vips)} active workflows from database")
            
        except Exception as e:
            logger.error(f"Error recovering workflows: {e}", exc_info=True)
        finally:
            db.close()
    
    def get_active_workflows(self) -> Dict[str, VIPState]:
        """
        Get all active workflows.
        
        Returns:
            Dictionary mapping VIP IDs to their current states
        """
        return self._active_workflows.copy()
