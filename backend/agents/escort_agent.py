"""
Escort Agent for AURA-VIP Orchestration System.

This module implements escort assignment and management.
Validates Requirements 3.1, 3.2, 3.3, 3.4, 3.5
"""

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from backend.models.schemas import Event, EventType, EscortStatus, VIPState
from backend.orchestrator.event_bus import EventBus
from backend.database.connection import SessionLocal
from backend.database.models import EscortDB

logger = logging.getLogger(__name__)


class EscortAgent:
    """
    Escort Agent responsible for escort assignment and management.
    
    Responsibilities:
    - Maintain escort availability pool
    - Assign escorts to VIPs based on availability
    - Track escort assignments and workload
    - Release escorts when VIP journey completes
    """
    
    def __init__(self, event_bus: EventBus):
        """
        Initialize the Escort Agent.
        
        Args:
            event_bus: The event bus for publishing and subscribing to events
        """
        self.event_bus = event_bus
        self._request_queue: deque = deque()  # FIFO queue for pending requests
        self._processing_queue = False
        
        # Subscribe to relevant events
        self.event_bus.subscribe(EventType.VIP_DETECTED, self.handle_vip_detected)
        self.event_bus.subscribe(EventType.STATE_CHANGED, self.handle_state_changed)
        
        logger.info("Escort Agent initialized and subscribed to events")
    
    async def handle_vip_detected(self, event: Event) -> None:
        """
        Handle VIP_DETECTED event by assigning an escort.
        
        Args:
            event: The VIP_DETECTED event
        
        Validates: Requirements 3.1, 3.2, 3.4
        """
        vip_id = event.vip_id or event.payload.get("vip_id")
        
        if not vip_id:
            logger.error("VIP_DETECTED event missing vip_id")
            return
        
        logger.info(f"Handling VIP detected for VIP ID: {vip_id}")
        
        # Try to assign an escort
        await self.assign_escort_to_vip(vip_id)
    
    async def handle_state_changed(self, event: Event) -> None:
        """
        Handle STATE_CHANGED event to release escorts when VIP completes journey.
        
        Args:
            event: The STATE_CHANGED event
        
        Validates: Requirement 3.5
        """
        vip_id = event.vip_id or event.payload.get("vip_id")
        new_state = event.payload.get("new_state")
        
        if not vip_id or not new_state:
            logger.error("STATE_CHANGED event missing vip_id or new_state")
            return
        
        # Release escort when VIP reaches COMPLETED state
        if new_state == VIPState.COMPLETED.value:
            logger.info(f"VIP {vip_id} completed journey, releasing escort")
            await self.release_escort_by_vip(vip_id)
    
    async def find_available_escort(self) -> Optional[str]:
        """
        Find first available escort from pool.
        
        Returns:
            Escort ID if available, None otherwise
        
        Validates: Requirement 3.1
        """
        try:
            db = SessionLocal()
            try:
                # Query for escorts with status=available
                escort = db.query(EscortDB).filter(
                    EscortDB.status == EscortStatus.AVAILABLE.value
                ).first()
                
                if escort:
                    logger.info(f"Found available escort: {escort.name} (ID: {escort.id})")
                    return escort.id
                else:
                    logger.warning("No available escorts found")
                    return None
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to find available escort: {e}", exc_info=True)
            return None
    
    async def assign_escort(self, escort_id: str, vip_id: str) -> None:
        """
        Create escort assignment and update escort status.
        
        Args:
            escort_id: The ID of the escort to assign
            vip_id: The ID of the VIP to assign to
        
        Validates: Requirements 3.2, 3.4
        """
        try:
            db = SessionLocal()
            try:
                # Get the escort
                escort = db.query(EscortDB).filter(EscortDB.id == escort_id).first()
                
                if not escort:
                    logger.error(f"Escort {escort_id} not found")
                    return
                
                # Update escort status and assignment
                escort.status = EscortStatus.ASSIGNED.value
                escort.assigned_vip_id = vip_id
                
                db.commit()
                
                logger.info(f"Assigned escort {escort.name} (ID: {escort_id}) to VIP {vip_id}")
                
                # Emit ESCORT_ASSIGNED event
                event = Event(
                    event_type=EventType.ESCORT_ASSIGNED,
                    payload={
                        "escort_id": escort_id,
                        "escort_name": escort.name,
                        "vip_id": vip_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    },
                    source_agent="escort_agent",
                    vip_id=vip_id
                )
                
                await self.event_bus.publish(event)
                
                logger.info(f"Emitted ESCORT_ASSIGNED event for VIP {vip_id}")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to assign escort: {e}", exc_info=True)
    
    async def assign_escort_to_vip(self, vip_id: str) -> None:
        """
        Assign an escort to a VIP, queueing the request if no escorts available.
        
        Args:
            vip_id: The ID of the VIP requesting an escort
        
        Validates: Requirements 3.1, 3.2, 3.3, 3.4
        """
        # Try to find an available escort
        escort_id = await self.find_available_escort()
        
        if escort_id:
            # Assign the escort
            await self.assign_escort(escort_id, vip_id)
        else:
            # No escorts available, queue the request
            logger.info(f"No escorts available, queueing request for VIP {vip_id}")
            self._request_queue.append(vip_id)
            logger.info(f"Request queue size: {len(self._request_queue)}")
    
    async def release_escort(self, escort_id: str) -> None:
        """
        Mark escort as available and process queued requests.
        
        Args:
            escort_id: The ID of the escort to release
        
        Validates: Requirement 3.5
        """
        try:
            db = SessionLocal()
            try:
                # Get the escort
                escort = db.query(EscortDB).filter(EscortDB.id == escort_id).first()
                
                if not escort:
                    logger.error(f"Escort {escort_id} not found")
                    return
                
                # Update escort status
                escort.status = EscortStatus.AVAILABLE.value
                escort.assigned_vip_id = None
                
                db.commit()
                
                logger.info(f"Released escort {escort.name} (ID: {escort_id})")
                
            finally:
                db.close()
            
            # Process queued requests
            await self.process_queue()
                
        except Exception as e:
            logger.error(f"Failed to release escort: {e}", exc_info=True)
    
    async def release_escort_by_vip(self, vip_id: str) -> None:
        """
        Release escort assigned to a specific VIP.
        
        Args:
            vip_id: The ID of the VIP whose escort should be released
        
        Validates: Requirement 3.5
        """
        try:
            db = SessionLocal()
            try:
                # Find escort assigned to this VIP
                escort = db.query(EscortDB).filter(
                    EscortDB.assigned_vip_id == vip_id
                ).first()
                
                if escort:
                    logger.info(f"Found escort {escort.name} (ID: {escort.id}) assigned to VIP {vip_id}")
                    await self.release_escort(escort.id)
                else:
                    logger.warning(f"No escort found assigned to VIP {vip_id}")
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to release escort by VIP: {e}", exc_info=True)
    
    async def process_queue(self) -> None:
        """
        Process queued escort requests in FIFO order.
        
        Validates: Requirement 3.3
        """
        # Prevent concurrent queue processing
        if self._processing_queue:
            return
        
        self._processing_queue = True
        
        try:
            while self._request_queue:
                # Check if an escort is available
                escort_id = await self.find_available_escort()
                
                if not escort_id:
                    # No escorts available, stop processing
                    logger.info("No escorts available to process queue")
                    break
                
                # Get the next VIP from the queue (FIFO)
                vip_id = self._request_queue.popleft()
                logger.info(f"Processing queued request for VIP {vip_id}")
                
                # Assign the escort
                await self.assign_escort(escort_id, vip_id)
                
        finally:
            self._processing_queue = False
