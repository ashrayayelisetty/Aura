"""
Flight Intelligence Agent for AURA-VIP Orchestration System.

This module implements flight monitoring, delay detection, and boarding alerts.
Validates Requirements 6.1, 6.2, 6.3, 6.4, 6.5
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from backend.models.schemas import Event, EventType, FlightStatus
from backend.orchestrator.event_bus import EventBus
from backend.database.connection import SessionLocal
from backend.database.models import FlightDB, VIPProfileDB

logger = logging.getLogger(__name__)


class FlightIntelligenceAgent:
    """
    Flight Intelligence Agent responsible for flight monitoring and boarding alerts.
    
    Responsibilities:
    - Monitor flight departure times
    - Detect flight delays and status changes
    - Emit boarding alerts 15 minutes before boarding
    - Coordinate with orchestrator for workflow adjustments
    """
    
    def __init__(self, event_bus: EventBus):
        """
        Initialize the Flight Intelligence Agent.
        
        Args:
            event_bus: The event bus for publishing and subscribing to events
        """
        self.event_bus = event_bus
        self._monitoring_task: Optional[asyncio.Task] = None
        self._stop_monitoring = False
        
        logger.info("Flight Intelligence Agent initialized")
    
    async def start_monitoring(self) -> None:
        """
        Start the flight monitoring loop.
        
        Validates: Requirement 6.1
        """
        if self._monitoring_task is not None:
            logger.warning("Flight monitoring already running")
            return
        
        self._stop_monitoring = False
        self._monitoring_task = asyncio.create_task(self.monitor_flights())
        logger.info("Flight monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop the flight monitoring loop."""
        if self._monitoring_task is None:
            logger.warning("Flight monitoring not running")
            return
        
        self._stop_monitoring = True
        
        # Wait for the monitoring task to complete
        if self._monitoring_task:
            try:
                await asyncio.wait_for(self._monitoring_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Flight monitoring task did not stop gracefully, cancelling")
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
        
        self._monitoring_task = None
        logger.info("Flight monitoring stopped")

    async def monitor_flights(self) -> None:
        """
        Continuous flight monitoring loop (check every 60 seconds).
        
        Validates: Requirement 6.1
        """
        logger.info("Starting flight monitoring loop")
        
        while not self._stop_monitoring:
            try:
                db = SessionLocal()
                try:
                    # Get all active flights (not departed or cancelled)
                    flights = db.query(FlightDB).filter(
                        FlightDB.status.in_([
                            FlightStatus.SCHEDULED.value,
                            FlightStatus.BOARDING.value,
                            FlightStatus.DELAYED.value
                        ])
                    ).all()
                    
                    for flight in flights:
                        # Check for boarding alerts
                        await self.check_boarding_time(flight.id)
                        
                        # Check for delays
                        await self.detect_delay(flight.id)
                    
                finally:
                    db.close()
                
            except Exception as e:
                logger.error(f"Error in flight monitoring loop: {e}", exc_info=True)
            
            # Wait 60 seconds before next check
            await asyncio.sleep(60)
        
        logger.info("Flight monitoring loop stopped")
    
    async def check_boarding_time(self, flight_id: str) -> None:
        """
        Check if boarding alert should be triggered (15 minutes before boarding).
        
        Args:
            flight_id: The ID of the flight to check
        
        Validates: Requirements 6.2, 14.4
        """
        try:
            db = SessionLocal()
            try:
                # Get the flight
                flight = db.query(FlightDB).filter(FlightDB.id == flight_id).first()
                
                if not flight:
                    logger.error(f"Flight {flight_id} not found")
                    return
                
                # Skip if flight is not scheduled or delayed
                if flight.status not in [FlightStatus.SCHEDULED.value, FlightStatus.DELAYED.value]:
                    return
                
                # Calculate time until boarding
                now = datetime.now(timezone.utc)
                
                # Ensure boarding_time is timezone-aware
                boarding_time = flight.boarding_time
                if boarding_time.tzinfo is None:
                    boarding_time = boarding_time.replace(tzinfo=timezone.utc)
                
                time_until_boarding = (boarding_time - now).total_seconds() / 60  # Convert to minutes
                
                # Emit boarding alert if within 15 minutes (with 1-minute tolerance)
                # We check if time is between 14 and 16 minutes to avoid duplicate alerts
                if 14 <= time_until_boarding <= 16:
                    logger.info(f"Boarding time approaching for flight {flight_id} ({time_until_boarding:.1f} minutes)")
                    await self.emit_boarding_alert(flight_id)
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to check boarding time for flight {flight_id}: {e}", exc_info=True)
    
    async def detect_delay(self, flight_id: str) -> Optional[datetime]:
        """
        Detect flight delay by comparing scheduled vs actual departure times.
        
        Args:
            flight_id: The ID of the flight to check
        
        Returns:
            New departure time if delay detected, None otherwise
        
        Validates: Requirement 6.3
        """
        try:
            db = SessionLocal()
            try:
                # Get the flight
                flight = db.query(FlightDB).filter(FlightDB.id == flight_id).first()
                
                if not flight:
                    logger.error(f"Flight {flight_id} not found")
                    return None
                
                # Check if delay_minutes has changed (indicating a new delay)
                # In a real system, this would compare against an external API
                # For this implementation, we detect if delay_minutes > 0 and status is still SCHEDULED
                if flight.delay_minutes > 0 and flight.status == FlightStatus.SCHEDULED.value:
                    # Calculate new departure time
                    departure_time = flight.departure_time
                    if departure_time.tzinfo is None:
                        departure_time = departure_time.replace(tzinfo=timezone.utc)
                    
                    new_departure_time = departure_time + timedelta(minutes=flight.delay_minutes)
                    
                    logger.info(f"Flight {flight_id} delayed by {flight.delay_minutes} minutes")
                    
                    # Update flight status to DELAYED
                    flight.status = FlightStatus.DELAYED.value
                    db.commit()
                    
                    # Emit FLIGHT_DELAY event
                    event = Event(
                        event_type=EventType.FLIGHT_DELAY,
                        payload={
                            "flight_id": flight_id,
                            "new_departure_time": new_departure_time.isoformat(),
                            "delay_minutes": flight.delay_minutes,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        },
                        source_agent="flight_intelligence_agent"
                    )
                    
                    await self.event_bus.publish(event)
                    
                    logger.info(f"Emitted FLIGHT_DELAY event for flight {flight_id}")
                    
                    return new_departure_time
                
                return None
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to detect delay for flight {flight_id}: {e}", exc_info=True)
            return None

    async def emit_boarding_alert(self, flight_id: str) -> None:
        """
        Emit BOARDING_ALERT event for all VIPs on the flight.
        
        Args:
            flight_id: The ID of the flight
        
        Validates: Requirements 6.2, 14.4
        """
        try:
            db = SessionLocal()
            try:
                # Get all VIPs on this flight
                vips = db.query(VIPProfileDB).filter(
                    VIPProfileDB.flight_id == flight_id
                ).all()
                
                if not vips:
                    logger.warning(f"No VIPs found for flight {flight_id}")
                    return
                
                # Get flight details
                flight = db.query(FlightDB).filter(FlightDB.id == flight_id).first()
                
                if not flight:
                    logger.error(f"Flight {flight_id} not found")
                    return
                
                # Emit BOARDING_ALERT event for each VIP
                for vip in vips:
                    event = Event(
                        event_type=EventType.BOARDING_ALERT,
                        payload={
                            "vip_id": vip.id,
                            "flight_id": flight_id,
                            "gate": flight.gate,
                            "boarding_time": flight.boarding_time.isoformat(),
                            "departure_time": flight.departure_time.isoformat(),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        },
                        source_agent="flight_intelligence_agent",
                        vip_id=vip.id
                    )
                    
                    await self.event_bus.publish(event)
                    
                    logger.info(f"Emitted BOARDING_ALERT event for VIP {vip.id} on flight {flight_id}")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to emit boarding alert for flight {flight_id}: {e}", exc_info=True)
