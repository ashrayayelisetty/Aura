"""
Lounge Agent for AURA-VIP Orchestration System.

This module implements lounge reservation management, capacity checking, and access control.
Validates Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 12.3, 12.4
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional, List
from collections import deque
from uuid import uuid4

import numpy as np
from scipy.spatial.distance import cosine

from backend.models.schemas import Event, EventType, ReservationStatus, VIPState
from backend.orchestrator.event_bus import EventBus
from backend.database.connection import SessionLocal
from backend.database.models import LoungeReservationDB, VIPProfileDB

logger = logging.getLogger(__name__)


class LoungeAgent:
    """
    Lounge Agent responsible for lounge reservation and access control.
    
    Responsibilities:
    - Create lounge reservations for VIPs
    - Verify face recognition at lounge entry
    - Track lounge occupancy and capacity
    - Manage reservation extensions for flight delays
    """
    
    def __init__(self, event_bus: EventBus):
        """
        Initialize the Lounge Agent.
        
        Args:
            event_bus: The event bus for publishing and subscribing to events
        """
        self.event_bus = event_bus
        
        # Get lounge capacity from environment variable
        self.max_capacity = int(os.getenv("LOUNGE_MAX_CAPACITY", "50"))
        self.default_duration = int(os.getenv("LOUNGE_DEFAULT_DURATION_MINUTES", "90"))
        self.confidence_threshold = float(os.getenv("FACE_CONFIDENCE_THRESHOLD", "0.85"))
        
        # Queue for reservations when at capacity
        self.reservation_queue: deque = deque()
        
        # Subscribe to relevant events
        self.event_bus.subscribe(EventType.VIP_DETECTED, self.handle_vip_detected)
        self.event_bus.subscribe(EventType.FLIGHT_DELAY, self.handle_flight_delay)
        self.event_bus.subscribe(EventType.STATE_CHANGED, self.handle_state_changed)
        
        logger.info(f"Lounge Agent initialized with capacity {self.max_capacity} and subscribed to events")

    async def handle_vip_detected(self, event: Event) -> None:
        """
        Handle VIP_DETECTED event by creating a lounge reservation.
        
        Args:
            event: The VIP_DETECTED event
        
        Validates: Requirement 5.1
        """
        vip_id = event.vip_id or event.payload.get("vip_id")
        
        if not vip_id:
            logger.error("VIP_DETECTED event missing vip_id")
            return
        
        logger.info(f"Handling VIP detected for VIP ID: {vip_id}")
        
        # Create lounge reservation
        await self.create_reservation(vip_id)

    async def handle_flight_delay(self, event: Event) -> None:
        """
        Handle FLIGHT_DELAY event by extending reservations.
        
        Args:
            event: The FLIGHT_DELAY event
        """
        vip_id = event.vip_id or event.payload.get("vip_id")
        delay_minutes = event.payload.get("delay_minutes", 0)
        
        if not vip_id:
            logger.error("FLIGHT_DELAY event missing vip_id")
            return
        
        logger.info(f"Handling flight delay for VIP {vip_id}: {delay_minutes} minutes")
        
        # Extend reservation
        await self.extend_reservation(vip_id, delay_minutes)

    async def handle_state_changed(self, event: Event) -> None:
        """
        Handle STATE_CHANGED event to grant lounge access or release reservations.
        
        Args:
            event: The STATE_CHANGED event
        
        Validates: Requirement 5.5
        """
        vip_id = event.vip_id or event.payload.get("vip_id")
        new_state = event.payload.get("new_state")
        
        if not vip_id or not new_state:
            logger.error("STATE_CHANGED event missing vip_id or new_state")
            return
        
        # Grant lounge access when VIP reaches LOUNGE_ENTRY state
        if new_state == VIPState.LOUNGE_ENTRY.value:
            logger.info(f"VIP {vip_id} reached LOUNGE_ENTRY state, granting access")
            await self.grant_access(vip_id)
        
        # Release reservation when VIP transitions to BUGGY_TO_GATE (departing lounge)
        elif new_state == VIPState.BUGGY_TO_GATE.value:
            logger.info(f"VIP {vip_id} departing lounge, releasing reservation")
            await self.release_reservation(vip_id)

    async def create_reservation(self, vip_id: str) -> None:
        """
        Create lounge reservation for VIP with capacity checking.
        
        Args:
            vip_id: The ID of the VIP requesting a reservation
        
        Validates: Requirements 5.1, 5.2
        """
        try:
            db = SessionLocal()
            try:
                # Check current occupancy
                current_occupancy = await self._get_current_occupancy()
                
                if current_occupancy >= self.max_capacity:
                    # Queue the reservation
                    logger.warning(f"Lounge at capacity ({current_occupancy}/{self.max_capacity}), queueing reservation for VIP {vip_id}")
                    self.reservation_queue.append(vip_id)
                    
                    # Calculate wait time estimate (assume 30 min average per VIP)
                    wait_time_minutes = len(self.reservation_queue) * 30
                    logger.info(f"VIP {vip_id} queued, estimated wait time: {wait_time_minutes} minutes")
                    
                    # TODO: Emit notification event for wait time
                    return
                
                # Create reservation
                reservation = LoungeReservationDB(
                    id=str(uuid4()),
                    vip_id=vip_id,
                    reservation_time=datetime.now(timezone.utc),
                    duration_minutes=self.default_duration,
                    status=ReservationStatus.RESERVED.value
                )
                
                db.add(reservation)
                db.commit()
                
                logger.info(f"Created lounge reservation {reservation.id} for VIP {vip_id}")
                
                # Emit LOUNGE_RESERVED event
                event = Event(
                    event_type=EventType.LOUNGE_RESERVED,
                    payload={
                        "reservation_id": reservation.id,
                        "vip_id": vip_id,
                        "duration_minutes": self.default_duration,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    },
                    source_agent="lounge_agent",
                    vip_id=vip_id
                )
                
                await self.event_bus.publish(event)
                
                logger.info(f"Emitted LOUNGE_RESERVED event for VIP {vip_id}")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to create reservation: {e}", exc_info=True)

    async def verify_lounge_entry(self, face_embedding: np.ndarray) -> Optional[str]:
        """
        Verify VIP at lounge entry via face recognition.
        
        Args:
            face_embedding: The face embedding to verify
        
        Returns:
            VIP ID if verification succeeds, None otherwise
        
        Validates: Requirement 5.3
        """
        try:
            db = SessionLocal()
            try:
                # Get all VIPs with active reservations
                active_reservations = db.query(LoungeReservationDB).filter(
                    LoungeReservationDB.status == ReservationStatus.RESERVED.value
                ).all()
                
                if not active_reservations:
                    logger.warning("No active reservations found")
                    return None
                
                # Get VIP IDs with active reservations
                vip_ids = [res.vip_id for res in active_reservations]
                
                # Get VIP profiles for matching
                vip_profiles = db.query(VIPProfileDB).filter(
                    VIPProfileDB.id.in_(vip_ids)
                ).all()
                
                # Match face embedding against VIP profiles
                best_match_vip_id = None
                best_confidence = 0.0
                
                for vip in vip_profiles:
                    # Deserialize face embedding
                    stored_embedding = np.frombuffer(vip.face_embedding, dtype=np.float64)
                    
                    # Calculate cosine similarity
                    similarity = 1 - cosine(face_embedding, stored_embedding)
                    
                    if similarity > best_confidence:
                        best_confidence = similarity
                        best_match_vip_id = vip.id
                
                # Check if confidence exceeds threshold
                if best_confidence >= self.confidence_threshold:
                    logger.info(f"Face verification succeeded for VIP {best_match_vip_id} with confidence {best_confidence:.2f}")
                    return best_match_vip_id
                else:
                    logger.warning(f"Face verification failed, best confidence: {best_confidence:.2f}")
                    return None
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to verify lounge entry: {e}", exc_info=True)
            return None

    async def grant_access(self, vip_id: str) -> None:
        """
        Grant lounge access and update occupancy.
        
        Args:
            vip_id: The ID of the VIP to grant access
        
        Validates: Requirements 5.4, 12.3
        """
        try:
            db = SessionLocal()
            try:
                # Find the reservation
                reservation = db.query(LoungeReservationDB).filter(
                    LoungeReservationDB.vip_id == vip_id,
                    LoungeReservationDB.status == ReservationStatus.RESERVED.value
                ).first()
                
                if not reservation:
                    logger.error(f"No active reservation found for VIP {vip_id}")
                    return
                
                # Update reservation status and entry time
                reservation.status = ReservationStatus.ACTIVE.value
                reservation.entry_time = datetime.now(timezone.utc)
                
                db.commit()
                
                logger.info(f"Granted lounge access to VIP {vip_id}, reservation {reservation.id} now active")
                
                # Emit LOUNGE_ENTRY event
                event = Event(
                    event_type=EventType.LOUNGE_ENTRY,
                    payload={
                        "reservation_id": reservation.id,
                        "vip_id": vip_id,
                        "entry_time": reservation.entry_time.isoformat(),
                        "occupancy": await self._get_current_occupancy(),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    },
                    source_agent="lounge_agent",
                    vip_id=vip_id
                )
                
                await self.event_bus.publish(event)
                
                logger.info(f"Emitted LOUNGE_ENTRY event for VIP {vip_id}")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to grant access: {e}", exc_info=True)

    async def extend_reservation(self, vip_id: str, additional_minutes: int) -> None:
        """
        Extend reservation due to flight delay.
        
        Args:
            vip_id: The ID of the VIP
            additional_minutes: Additional minutes to extend the reservation
        
        Validates: Requirement 5.5
        """
        try:
            db = SessionLocal()
            try:
                # Find active reservation
                reservation = db.query(LoungeReservationDB).filter(
                    LoungeReservationDB.vip_id == vip_id,
                    LoungeReservationDB.status.in_([
                        ReservationStatus.RESERVED.value,
                        ReservationStatus.ACTIVE.value
                    ])
                ).first()
                
                if not reservation:
                    logger.warning(f"No active reservation found for VIP {vip_id}")
                    return
                
                # Extend duration
                old_duration = reservation.duration_minutes
                reservation.duration_minutes += additional_minutes
                
                db.commit()
                
                logger.info(f"Extended reservation {reservation.id} for VIP {vip_id} from {old_duration} to {reservation.duration_minutes} minutes")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to extend reservation: {e}", exc_info=True)

    async def release_reservation(self, vip_id: str) -> None:
        """
        Release reservation and decrement occupancy.
        
        Args:
            vip_id: The ID of the VIP departing the lounge
        
        Validates: Requirements 5.5, 12.4
        """
        try:
            db = SessionLocal()
            try:
                # Find active reservation
                reservation = db.query(LoungeReservationDB).filter(
                    LoungeReservationDB.vip_id == vip_id,
                    LoungeReservationDB.status == ReservationStatus.ACTIVE.value
                ).first()
                
                if not reservation:
                    logger.warning(f"No active reservation found for VIP {vip_id}")
                    return
                
                # Update reservation status and exit time
                reservation.status = ReservationStatus.COMPLETED.value
                reservation.exit_time = datetime.now(timezone.utc)
                
                db.commit()
                
                logger.info(f"Released reservation {reservation.id} for VIP {vip_id}")
                
                # Emit event to notify frontend of lounge update
                event = Event(
                    event_type=EventType.LOUNGE_ENTRY,  # Reuse for lounge updates
                    payload={
                        "reservation_id": reservation.id,
                        "vip_id": vip_id,
                        "exit_time": reservation.exit_time.isoformat(),
                        "occupancy": await self._get_current_occupancy(),
                        "action": "released",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    },
                    source_agent="lounge_agent",
                    vip_id=vip_id
                )
                await self.event_bus.publish(event)
                
                # Process queued reservations if any
                if self.reservation_queue:
                    next_vip_id = self.reservation_queue.popleft()
                    logger.info(f"Processing queued reservation for VIP {next_vip_id}")
                    await self.create_reservation(next_vip_id)
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to release reservation: {e}", exc_info=True)

    async def _get_current_occupancy(self) -> int:
        """
        Get current lounge occupancy count.
        
        Returns:
            Number of VIPs currently in the lounge
        
        Validates: Requirements 12.3, 12.4
        """
        try:
            db = SessionLocal()
            try:
                # Count active reservations (VIPs currently in lounge)
                count = db.query(LoungeReservationDB).filter(
                    LoungeReservationDB.status == ReservationStatus.ACTIVE.value
                ).count()
                
                return count
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to get current occupancy: {e}", exc_info=True)
            return 0
