"""
AURA-VIP Orchestration System - Main Application Entry Point

This module initializes the FastAPI application, sets up all agents,
and configures WebSocket endpoints for real-time communication.

Validates Requirements 8.1, 8.4, 9.1, 10.1, 11.1, 12.1, 18.2
"""

import logging
from contextlib import asynccontextmanager
from typing import List
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.database.connection import create_tables, get_db, SessionLocal
from backend.database.models import (
    VIPProfileDB, EscortDB, BuggyDB, FlightDB, 
    LoungeReservationDB, ServiceLogDB
)
from backend.models.schemas import (
    VIPProfile, Escort, Buggy, Flight, 
    LoungeReservation, ServiceLog, EventType, VIPState
)
from backend.orchestrator.event_bus import EventBus
from backend.orchestrator.master_orchestrator import MasterOrchestrator
from backend.websocket.manager import WebSocketManager
from backend.agents.identity_agent import IdentityAgent
from backend.agents.escort_agent import EscortAgent
from backend.agents.transport_agent import TransportAgent
from backend.agents.lounge_agent import LoungeAgent
from backend.agents.flight_intelligence_agent import FlightIntelligenceAgent
from backend.agents.baggage_agent import BaggageAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
event_bus: EventBus = None
orchestrator: MasterOrchestrator = None
websocket_manager: WebSocketManager = None
agents = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager - initializes and cleans up resources.
    
    Initializes:
    - Database tables
    - Event Bus
    - Master Orchestrator
    - WebSocket Manager
    - All agents (Identity, Escort, Transport, Lounge, Flight Intelligence, Baggage)
    
    Validates: Requirement 18.2
    """
    global event_bus, orchestrator, websocket_manager, agents
    
    logger.info("Starting AURA-VIP Orchestration System...")
    
    # Create database tables
    create_tables()
    logger.info("Database tables created")
    
    # Initialize sample data (escorts, buggies, flights)
    from backend.database.init_db import create_sample_data
    try:
        create_sample_data()
        logger.info("Sample data initialized")
    except Exception as e:
        logger.warning(f"Sample data initialization skipped (may already exist): {e}")
    
    # Initialize Event Bus
    event_bus = EventBus()
    logger.info("Event Bus initialized")
    
    # Initialize Master Orchestrator
    orchestrator = MasterOrchestrator(event_bus)
    logger.info("Master Orchestrator initialized")
    
    # Initialize WebSocket Manager
    websocket_manager = WebSocketManager()
    logger.info("WebSocket Manager initialized")
    
    # Connect Event Bus to WebSocket Manager
    # Subscribe WebSocket Manager to all event types
    for event_type in EventType:
        event_bus.subscribe(event_type, websocket_manager.handle_event)
    logger.info("Event Bus connected to WebSocket Manager")
    
    # Initialize all agents
    agents['identity'] = IdentityAgent(event_bus)
    agents['escort'] = EscortAgent(event_bus)
    agents['transport'] = TransportAgent(event_bus)
    agents['lounge'] = LoungeAgent(event_bus)
    agents['flight_intelligence'] = FlightIntelligenceAgent(event_bus)
    agents['baggage'] = BaggageAgent(event_bus)
    logger.info("All agents initialized")
    
    # Recover active workflows from database
    await orchestrator.recover_workflows()
    logger.info("Active workflows recovered")
    
    logger.info("AURA-VIP System startup complete")
    
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down AURA-VIP System...")
    await websocket_manager.close_all()
    logger.info("AURA-VIP System shutdown complete")


app = FastAPI(
    title="AURA-VIP Orchestration System",
    description="AI-powered airport VIP concierge system",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health Check Endpoints
# ============================================================================


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "AURA-VIP System Online", "version": "1.0.0"}


@app.get("/api/health")
async def health_check():
    """Detailed health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "database": "connected",
            "event_bus": "active",
            "orchestrator": "active",
            "websocket": f"{websocket_manager.get_connection_count()} connections",
            "agents": len(agents)
        }
    }


# ============================================================================
# VIP Endpoints
# ============================================================================


@app.get("/api/vips", response_model=List[dict])
async def list_vips(db: Session = Depends(get_db)):
    """
    List all VIPs with current state.
    
    Returns:
        List of VIP profiles with current state and assignments
    
    Validates: Requirements 8.1, 8.4
    """
    vips = db.query(VIPProfileDB).all()
    
    result = []
    for vip in vips:
        # Get escort assignment
        escort = db.query(EscortDB).filter(EscortDB.assigned_vip_id == vip.id).first()
        
        # Get buggy assignment
        buggy = db.query(BuggyDB).filter(BuggyDB.assigned_vip_id == vip.id).first()
        
        # Get lounge reservation
        lounge = db.query(LoungeReservationDB).filter(
            LoungeReservationDB.vip_id == vip.id,
            LoungeReservationDB.status.in_(["reserved", "active"])
        ).first()
        
        result.append({
            "id": vip.id,
            "name": vip.name,
            "flight_id": vip.flight_id,
            "current_state": vip.current_state,
            "escort": {
                "id": escort.id,
                "name": escort.name
            } if escort else None,
            "buggy": {
                "id": buggy.id,
                "battery_level": buggy.battery_level
            } if buggy else None,
            "lounge": {
                "id": lounge.id,
                "status": lounge.status
            } if lounge else None,
            "created_at": vip.created_at.isoformat(),
            "updated_at": vip.updated_at.isoformat()
        })
    
    return result


@app.get("/api/vips/{vip_id}", response_model=dict)
async def get_vip_details(vip_id: str, db: Session = Depends(get_db)):
    """
    Get VIP details and timeline.
    
    Args:
        vip_id: The VIP identifier
    
    Returns:
        VIP profile with complete timeline and service logs
    
    Validates: Requirements 9.1, 9.2, 9.3, 9.4
    """
    vip = db.query(VIPProfileDB).filter(VIPProfileDB.id == vip_id).first()
    
    if not vip:
        return {"error": "VIP not found"}
    
    # Get escort assignment
    escort = db.query(EscortDB).filter(EscortDB.assigned_vip_id == vip.id).first()
    
    # Get buggy assignment
    buggy = db.query(BuggyDB).filter(BuggyDB.assigned_vip_id == vip.id).first()
    
    # Get lounge reservation
    lounge = db.query(LoungeReservationDB).filter(
        LoungeReservationDB.vip_id == vip.id
    ).first()
    
    # Get flight information
    flight = db.query(FlightDB).filter(FlightDB.id == vip.flight_id).first()
    
    # Get service logs (timeline) in chronological order
    service_logs = db.query(ServiceLogDB).filter(
        ServiceLogDB.vip_id == vip.id
    ).order_by(ServiceLogDB.timestamp.asc()).all()
    
    timeline = []
    for log in service_logs:
        timeline.append({
            "id": log.id,
            "event_type": log.event_type,
            "event_data": log.event_data,
            "timestamp": log.timestamp.isoformat(),
            "agent_source": log.agent_source
        })
    
    return {
        "id": vip.id,
        "name": vip.name,
        "flight_id": vip.flight_id,
        "current_state": vip.current_state,
        "escort": {
            "id": escort.id,
            "name": escort.name,
            "status": escort.status
        } if escort else None,
        "buggy": {
            "id": buggy.id,
            "battery_level": buggy.battery_level,
            "status": buggy.status,
            "current_location": buggy.current_location
        } if buggy else None,
        "lounge": {
            "id": lounge.id,
            "status": lounge.status,
            "reservation_time": lounge.reservation_time.isoformat(),
            "entry_time": lounge.entry_time.isoformat() if lounge.entry_time else None,
            "exit_time": lounge.exit_time.isoformat() if lounge.exit_time else None,
            "duration_minutes": lounge.duration_minutes
        } if lounge else None,
        "flight": {
            "id": flight.id,
            "departure_time": flight.departure_time.isoformat(),
            "boarding_time": flight.boarding_time.isoformat(),
            "status": flight.status,
            "gate": flight.gate,
            "destination": flight.destination,
            "delay_minutes": flight.delay_minutes
        } if flight else None,
        "timeline": timeline,
        "created_at": vip.created_at.isoformat(),
        "updated_at": vip.updated_at.isoformat()
    }


# ============================================================================
# Escort Endpoints
# ============================================================================


@app.get("/api/escorts", response_model=List[dict])
async def list_escorts(db: Session = Depends(get_db)):
    """
    List all escorts with status.
    
    Returns:
        List of escorts with current status and assignments
    
    Validates: Requirements 10.1
    """
    escorts = db.query(EscortDB).all()
    
    result = []
    for escort in escorts:
        # Get assigned VIP if any
        vip = None
        if escort.assigned_vip_id:
            vip = db.query(VIPProfileDB).filter(VIPProfileDB.id == escort.assigned_vip_id).first()
        
        result.append({
            "id": escort.id,
            "name": escort.name,
            "status": escort.status,
            "assigned_vip": {
                "id": vip.id,
                "name": vip.name,
                "current_state": vip.current_state
            } if vip else None,
            "created_at": escort.created_at.isoformat()
        })
    
    return result


# ============================================================================
# Buggy Endpoints
# ============================================================================


@app.get("/api/buggies", response_model=List[dict])
async def list_buggies(db: Session = Depends(get_db)):
    """
    List all buggies with battery and status.
    
    Returns:
        List of buggies with battery level, status, and assignments
    
    Validates: Requirements 11.1
    """
    buggies = db.query(BuggyDB).all()
    
    result = []
    for buggy in buggies:
        # Get assigned VIP if any
        vip = None
        if buggy.assigned_vip_id:
            vip = db.query(VIPProfileDB).filter(VIPProfileDB.id == buggy.assigned_vip_id).first()
        
        result.append({
            "id": buggy.id,
            "battery_level": buggy.battery_level,
            "status": buggy.status,
            "current_location": buggy.current_location,
            "assigned_vip": {
                "id": vip.id,
                "name": vip.name,
                "current_state": vip.current_state
            } if vip else None,
            "created_at": buggy.created_at.isoformat()
        })
    
    return result


# ============================================================================
# Lounge Endpoints
# ============================================================================


@app.get("/api/lounge", response_model=dict)
async def get_lounge_status(db: Session = Depends(get_db)):
    """
    Get lounge occupancy and reservations.
    
    Returns:
        Lounge status with occupancy count and active reservations
    
    Validates: Requirements 12.1
    """
    # Get active reservations
    active_reservations = db.query(LoungeReservationDB).filter(
        LoungeReservationDB.status.in_(["reserved", "active"])
    ).all()
    
    # Count current occupancy (active status means VIP is in lounge)
    occupancy = db.query(LoungeReservationDB).filter(
        LoungeReservationDB.status == "active"
    ).count()
    
    # Get lounge capacity from environment or use default
    import os
    capacity = int(os.getenv("LOUNGE_CAPACITY", "50"))
    
    reservations = []
    for reservation in active_reservations:
        vip = db.query(VIPProfileDB).filter(VIPProfileDB.id == reservation.vip_id).first()
        reservations.append({
            "id": reservation.id,
            "vip": {
                "id": vip.id,
                "name": vip.name
            } if vip else None,
            "status": reservation.status,
            "reservation_time": reservation.reservation_time.isoformat(),
            "entry_time": reservation.entry_time.isoformat() if reservation.entry_time else None,
            "duration_minutes": reservation.duration_minutes
        })
    
    return {
        "occupancy": occupancy,
        "capacity": capacity,
        "utilization_percent": round((occupancy / capacity) * 100, 1) if capacity > 0 else 0,
        "reservations": reservations
    }


# ============================================================================
# Flight Endpoints
# ============================================================================


@app.get("/api/flights", response_model=List[dict])
async def list_flights(db: Session = Depends(get_db)):
    """
    List all flights with status.
    
    Returns:
        List of flights with status and VIP assignments
    
    Validates: Requirements 8.1
    """
    flights = db.query(FlightDB).all()
    
    result = []
    for flight in flights:
        # Get VIPs on this flight
        vips = db.query(VIPProfileDB).filter(VIPProfileDB.flight_id == flight.id).all()
        
        vip_list = []
        for vip in vips:
            vip_list.append({
                "id": vip.id,
                "name": vip.name,
                "current_state": vip.current_state
            })
        
        result.append({
            "id": flight.id,
            "departure_time": flight.departure_time.isoformat(),
            "boarding_time": flight.boarding_time.isoformat(),
            "status": flight.status,
            "gate": flight.gate,
            "destination": flight.destination,
            "delay_minutes": flight.delay_minutes,
            "vips": vip_list,
            "created_at": flight.created_at.isoformat()
        })
    
    return result


# ============================================================================
# Demo Mode Endpoints
# ============================================================================


@app.post("/api/demo/start")
async def start_demo(db: Session = Depends(get_db)):
    """
    Start demo mode - simulate complete VIP journey.
    
    Simulates:
    - VIP arrival through face detection
    - Auto-progress through all workflow states with realistic delays (30s between states)
    - Flight delay at LOUNGE_ENTRY state (add 30 min delay)
    - Boarding alert 15 minutes before boarding
    - Real-time dashboard updates
    
    Returns:
        Demo status and VIP ID
    
    Validates: Requirements 19.1, 19.2, 19.3, 19.4, 19.5
    """
    import asyncio
    from datetime import timedelta
    import numpy as np
    import pickle
    
    logger.info("Starting demo mode...")
    
    # Create demo VIP profile
    demo_vip_id = str(uuid4())
    demo_flight_id = "DM001"
    
    # Create demo flight
    now = datetime.now(timezone.utc)
    departure_time = now + timedelta(hours=2)
    boarding_time = departure_time - timedelta(minutes=30)
    
    demo_flight = FlightDB(
        id=demo_flight_id,
        departure_time=departure_time,
        boarding_time=boarding_time,
        status="scheduled",
        gate="A15",
        destination="Dubai",
        delay_minutes=0,
        created_at=now
    )
    
    # Check if flight already exists
    existing_flight = db.query(FlightDB).filter(FlightDB.id == demo_flight_id).first()
    if not existing_flight:
        db.add(demo_flight)
    else:
        # Update existing flight
        existing_flight.departure_time = departure_time
        existing_flight.boarding_time = boarding_time
        existing_flight.status = "scheduled"
        existing_flight.delay_minutes = 0
    
    db.commit()
    
    # Create demo VIP with face embedding (pickled numpy array)
    demo_embedding = np.random.rand(128)
    
    demo_vip = VIPProfileDB(
        id=demo_vip_id,
        name="Demo VIP Guest",
        face_embedding=pickle.dumps(demo_embedding),  # Pickle the numpy array
        flight_id=demo_flight_id,
        current_state="prepared",
        created_at=now,
        updated_at=now
    )
    
    db.add(demo_vip)
    db.commit()
    
    logger.info(f"Created demo VIP: {demo_vip_id} on flight {demo_flight_id}")
    
    # Start async demo workflow
    asyncio.create_task(_run_demo_workflow(demo_vip_id, demo_flight_id))
    
    return {
        "status": "demo_started",
        "vip_id": demo_vip_id,
        "flight_id": demo_flight_id,
        "message": "Demo workflow started. VIP will progress through all states automatically."
    }


@app.post("/api/demo/reset")
async def reset_demo(db: Session = Depends(get_db)):
    """
    Reset demo mode - clear all VIP states and resource assignments.
    
    Clears:
    - All VIP profiles
    - All resource assignments (escorts, buggies, lounge reservations)
    - All service logs
    - Resets all resources to available status
    
    Returns:
        Reset status
    
    Validates: Requirement 19.5
    """
    logger.info("Resetting demo mode...")
    
    try:
        # Clear all VIP profiles
        db.query(VIPProfileDB).delete()
        
        # Clear all service logs
        db.query(ServiceLogDB).delete()
        
        # Clear all lounge reservations
        db.query(LoungeReservationDB).delete()
        
        # Reset all escorts to available
        escorts = db.query(EscortDB).all()
        for escort in escorts:
            escort.status = "available"
            escort.assigned_vip_id = None
        
        # Reset all buggies to available
        buggies = db.query(BuggyDB).all()
        for buggy in buggies:
            buggy.status = "available"
            buggy.assigned_vip_id = None
            buggy.current_location = "idle"
            buggy.battery_level = 100  # Recharge all buggies
        
        # Clear demo flights
        db.query(FlightDB).filter(FlightDB.id.like("DM%")).delete()
        
        db.commit()
        
        # Clear orchestrator's active workflows
        orchestrator._active_workflows.clear()
        
        logger.info("Demo mode reset complete")
        
        return {
            "status": "demo_reset",
            "message": "All VIP states and resource assignments cleared"
        }
    
    except Exception as e:
        logger.error(f"Error resetting demo: {e}", exc_info=True)
        db.rollback()
        return {
            "status": "error",
            "message": f"Failed to reset demo: {str(e)}"
        }


async def _run_demo_workflow(vip_id: str, flight_id: str):
    """
    Run the demo workflow - auto-progress through all states.
    Enhanced with detailed processing logs for realistic demo.
    
    Args:
        vip_id: The demo VIP identifier
        flight_id: The demo flight identifier
    
    Validates: Requirements 19.2, 19.3, 19.4
    """
    import asyncio
    from datetime import timedelta
    from backend.models.schemas import Event, EventType
    
    logger.info(f"Starting demo workflow for VIP {vip_id}")
    
    try:
        # Step 1: Simulate VIP arrival with detailed face recognition process
        await asyncio.sleep(2)  # Initial delay
        logger.info(f"Demo: Camera feed activated at Terminal Entrance")
        await asyncio.sleep(0.5)
        
        logger.info(f"Demo: Face detected in frame - extracting features...")
        await asyncio.sleep(0.8)
        
        logger.info(f"Demo: Face embedding extracted (512 dimensions)")
        await asyncio.sleep(0.5)
        
        logger.info(f"Demo: Comparing against VIP database (3 profiles)...")
        await asyncio.sleep(1.0)
        
        logger.info(f"Demo: Match found! Confidence: 95.2% - Simulating VIP detection for {vip_id}")
        
        vip_detected_event = Event(
            event_type=EventType.VIP_DETECTED,
            payload={
                "vip_id": vip_id,
                "confidence": 0.952,
                "detection_location": "Terminal Entrance",
                "face_embedding_dimensions": 512,
                "processing_time_ms": 234
            },
            source_agent="identity_agent",
            vip_id=vip_id
        )
        await event_bus.publish(vip_detected_event)
        logger.info(f"Demo: VIP_DETECTED event published to Event Bus")
        
        # Step 2: ARRIVED -> BUGGY_PICKUP
        await asyncio.sleep(5)
        logger.info(f"Demo: Master Orchestrator processing state transition...")
        await asyncio.sleep(0.5)
        logger.info(f"Demo: Validating state sequence: ARRIVED → BUGGY_PICKUP")
        await asyncio.sleep(0.3)
        logger.info(f"Demo: Transitioning {vip_id} to BUGGY_PICKUP")
        await orchestrator.transition_state(vip_id, VIPState.BUGGY_PICKUP)
        
        # Step 3: BUGGY_PICKUP -> CHECKED_IN
        await asyncio.sleep(5)
        logger.info(f"Demo: Buggy transport simulation - 5 minute journey")
        await asyncio.sleep(0.5)
        logger.info(f"Demo: Battery depletion: 5% consumed")
        await asyncio.sleep(0.5)
        logger.info(f"Demo: Transitioning {vip_id} to CHECKED_IN")
        await orchestrator.transition_state(vip_id, VIPState.CHECKED_IN)
        
        # Step 4: CHECKED_IN -> SECURITY_CLEARED
        await asyncio.sleep(5)
        logger.info(f"Demo: Baggage Agent generating priority tag...")
        await asyncio.sleep(0.8)
        logger.info(f"Demo: Priority tag generated - routing to fast track")
        await asyncio.sleep(0.5)
        logger.info(f"Demo: Transitioning {vip_id} to SECURITY_CLEARED")
        try:
            await orchestrator.transition_state(vip_id, VIPState.SECURITY_CLEARED)
            logger.info(f"Demo: Successfully transitioned to SECURITY_CLEARED")
        except Exception as e:
            logger.error(f"Demo: Error transitioning to SECURITY_CLEARED: {e}", exc_info=True)
        
        # Step 5: SECURITY_CLEARED -> LOUNGE_ENTRY
        await asyncio.sleep(5)
        logger.info(f"Demo: Lounge Agent checking capacity...")
        await asyncio.sleep(0.5)
        logger.info(f"Demo: Capacity available - creating reservation")
        await asyncio.sleep(0.5)
        logger.info(f"Demo: Transitioning {vip_id} to LOUNGE_ENTRY")
        try:
            await orchestrator.transition_state(vip_id, VIPState.LOUNGE_ENTRY)
            logger.info(f"Demo: Successfully transitioned to LOUNGE_ENTRY")
        except Exception as e:
            logger.error(f"Demo: Error transitioning to LOUNGE_ENTRY: {e}", exc_info=True)
        
        # Step 6: Simulate flight delay at LOUNGE_ENTRY
        await asyncio.sleep(6)
        logger.info(f"Demo: Flight Intelligence Agent monitoring flight {flight_id}")
        await asyncio.sleep(0.8)
        logger.info(f"Demo: Delay detected - comparing scheduled vs actual departure")
        await asyncio.sleep(0.5)
        logger.info(f"Demo: Simulating flight delay for {flight_id}")
        
        db = SessionLocal()
        try:
            flight = db.query(FlightDB).filter(FlightDB.id == flight_id).first()
            if flight:
                # Add 30 minute delay
                flight.delay_minutes = 30
                flight.departure_time = flight.departure_time + timedelta(minutes=30)
                flight.boarding_time = flight.boarding_time + timedelta(minutes=30)
                flight.status = "delayed"
                db.commit()
                
                logger.info(f"Demo: Flight {flight_id} delayed by 30 minutes - updating database")
                await asyncio.sleep(0.5)
                
                # Emit FLIGHT_DELAY event
                flight_delay_event = Event(
                    event_type=EventType.FLIGHT_DELAY,
                    payload={
                        "flight_id": flight_id,
                        "delay_minutes": 30,
                        "new_departure_time": flight.departure_time.isoformat(),
                        "new_boarding_time": flight.boarding_time.isoformat(),
                        "reason": "Air traffic control delay"
                    },
                    source_agent="flight_intelligence_agent",
                    vip_id=vip_id
                )
                await event_bus.publish(flight_delay_event)
                logger.info(f"Demo: FLIGHT_DELAY event published - extending lounge time")
        finally:
            db.close()
        
        # Step 7: Simulate boarding alert (15 minutes before boarding)
        await asyncio.sleep(6)
        logger.info(f"Demo: Flight Intelligence Agent calculating boarding time...")
        await asyncio.sleep(0.5)
        logger.info(f"Demo: Boarding alert threshold reached (15 minutes)")
        await asyncio.sleep(0.5)
        logger.info(f"Demo: Simulating boarding alert for {flight_id}")
        
        boarding_alert_event = Event(
            event_type=EventType.BOARDING_ALERT,
            payload={
                "flight_id": flight_id,
                "gate": "A15",
                "boarding_time": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
                "vip_ids": [vip_id],
                "alert_type": "15_minute_warning"
            },
            source_agent="flight_intelligence_agent",
            vip_id=vip_id
        )
        await event_bus.publish(boarding_alert_event)
        logger.info(f"Demo: BOARDING_ALERT event published")
        
        # Step 8: LOUNGE_ENTRY -> BUGGY_TO_GATE
        await asyncio.sleep(6)
        logger.info(f"Demo: Transport Agent dispatching buggy to gate...")
        await asyncio.sleep(0.8)
        logger.info(f"Demo: Route calculated: Lounge → Gate A15 (7 minutes)")
        await asyncio.sleep(0.5)
        logger.info(f"Demo: Transitioning {vip_id} to BUGGY_TO_GATE")
        await orchestrator.transition_state(vip_id, VIPState.BUGGY_TO_GATE)
        
        # Step 9: BUGGY_TO_GATE -> BOARDED
        await asyncio.sleep(6)
        logger.info(f"Demo: VIP arrived at gate - boarding process initiated")
        await asyncio.sleep(0.5)
        logger.info(f"Demo: Transitioning {vip_id} to BOARDED")
        await orchestrator.transition_state(vip_id, VIPState.BOARDED)
        
        # Step 10: BOARDED -> COMPLETED
        await asyncio.sleep(6)
        logger.info(f"Demo: VIP successfully boarded - releasing resources...")
        await asyncio.sleep(0.8)
        logger.info(f"Demo: Escort released - status updated to available")
        await asyncio.sleep(0.3)
        logger.info(f"Demo: Buggy released - returning to idle location")
        await asyncio.sleep(0.3)
        logger.info(f"Demo: Lounge reservation closed - occupancy updated")
        await asyncio.sleep(0.5)
        logger.info(f"Demo: Transitioning {vip_id} to COMPLETED")
        await orchestrator.transition_state(vip_id, VIPState.COMPLETED)
        
        logger.info(f"Demo workflow completed successfully for VIP {vip_id}")
        
    except Exception as e:
        logger.error(f"Error in demo workflow for VIP {vip_id}: {e}", exc_info=True)


# ============================================================================
# WebSocket Endpoint
# ============================================================================


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.
    
    Accepts WebSocket connections and pushes real-time updates
    for all system events.
    
    Validates: Requirements 16.1, 16.2, 16.3
    """
    await websocket_manager.connect(websocket)
    logger.info("WebSocket client connected")
    
    try:
        # Keep connection alive and handle incoming messages
        while True:
            # Wait for messages from client (ping/pong, etc.)
            data = await websocket.receive_text()
            logger.debug(f"Received WebSocket message: {data}")
            
            # Echo back for ping/pong
            if data == "ping":
                await websocket.send_text("pong")
    
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        await websocket_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
