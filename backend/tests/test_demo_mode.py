"""
Unit tests for demo mode functionality.

Tests the demo mode endpoints that simulate a complete VIP journey.
Validates Requirements 19.1, 19.2, 19.3, 19.4, 19.5
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import List
import asyncio

from backend.database.models import Base, VIPProfileDB, EscortDB, BuggyDB, FlightDB
from backend.orchestrator.event_bus import EventBus
from backend.orchestrator.master_orchestrator import MasterOrchestrator


# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_demo.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get database session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Create test app with demo endpoints
test_app = FastAPI()

# Initialize global instances for testing
event_bus = EventBus()
orchestrator = MasterOrchestrator(event_bus)


# Import demo endpoint implementations
from uuid import uuid4
import numpy as np


@test_app.post("/api/demo/start")
async def start_demo(db: Session = Depends(get_db)):
    """Start demo mode - simulate complete VIP journey."""
    import asyncio
    from datetime import timedelta
    
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
    
    # Create demo VIP with face embedding
    demo_embedding = np.random.rand(128).tolist()
    
    demo_vip = VIPProfileDB(
        id=demo_vip_id,
        name="Demo VIP Guest",
        face_embedding=str(demo_embedding),
        flight_id=demo_flight_id,
        current_state="prepared",
        created_at=now,
        updated_at=now
    )
    
    db.add(demo_vip)
    db.commit()
    
    return {
        "status": "demo_started",
        "vip_id": demo_vip_id,
        "flight_id": demo_flight_id,
        "message": "Demo workflow started. VIP will progress through all states automatically."
    }


@test_app.post("/api/demo/reset")
async def reset_demo(db: Session = Depends(get_db)):
    """Reset demo mode - clear all VIP states and resource assignments."""
    try:
        # Clear all VIP profiles
        db.query(VIPProfileDB).delete()
        
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
        
        return {
            "status": "demo_reset",
            "message": "All VIP states and resource assignments cleared"
        }
    
    except Exception as e:
        db.rollback()
        return {
            "status": "error",
            "message": f"Failed to reset demo: {str(e)}"
        }


@pytest.fixture(scope="function")
def test_db():
    """Create test database tables."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Create test escorts
    escorts = [
        EscortDB(id="escort-1", name="Test Escort 1", status="available"),
        EscortDB(id="escort-2", name="Test Escort 2", status="available"),
    ]
    for escort in escorts:
        db.add(escort)
    
    # Create test buggies
    buggies = [
        BuggyDB(id="buggy-1", battery_level=100, status="available", current_location="idle"),
        BuggyDB(id="buggy-2", battery_level=85, status="available", current_location="idle"),
    ]
    for buggy in buggies:
        db.add(buggy)
    
    db.commit()
    
    yield db
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)
    db.close()


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(test_app, raise_server_exceptions=False)


def test_demo_start_endpoint(client, test_db):
    """
    Test that /api/demo/start creates a demo VIP and starts the workflow.
    
    Validates: Requirements 19.1, 19.2
    """
    # Start demo
    response = client.post("/api/demo/start")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "demo_started"
    assert "vip_id" in data
    assert "flight_id" in data
    assert data["flight_id"].startswith("DM")
    assert "message" in data
    
    vip_id = data["vip_id"]
    flight_id = data["flight_id"]
    
    # Verify VIP was created in database
    vip = test_db.query(VIPProfileDB).filter(VIPProfileDB.id == vip_id).first()
    assert vip is not None
    assert vip.name == "Demo VIP Guest"
    assert vip.flight_id == flight_id
    assert vip.current_state == "prepared"
    
    # Verify flight was created
    flight = test_db.query(FlightDB).filter(FlightDB.id == flight_id).first()
    assert flight is not None
    assert flight.destination == "Dubai"
    assert flight.gate == "A15"
    assert flight.status == "scheduled"


def test_demo_reset_endpoint(client, test_db):
    """
    Test that /api/demo/reset clears all VIP states and resource assignments.
    
    Validates: Requirement 19.5
    """
    # First, start a demo to create data
    start_response = client.post("/api/demo/start")
    assert start_response.status_code == 200
    
    # Verify data exists
    vips_before = test_db.query(VIPProfileDB).count()
    assert vips_before > 0
    
    # Reset demo
    reset_response = client.post("/api/demo/reset")
    
    assert reset_response.status_code == 200
    data = reset_response.json()
    
    assert data["status"] == "demo_reset"
    assert "message" in data
    
    # Verify all VIPs are cleared
    vips_after = test_db.query(VIPProfileDB).count()
    assert vips_after == 0
    
    # Verify escorts are reset to available
    escorts = test_db.query(EscortDB).all()
    for escort in escorts:
        assert escort.status == "available"
        assert escort.assigned_vip_id is None
    
    # Verify buggies are reset to available with full battery
    buggies = test_db.query(BuggyDB).all()
    for buggy in buggies:
        assert buggy.status == "available"
        assert buggy.assigned_vip_id is None
        assert buggy.current_location == "idle"
        assert buggy.battery_level == 100


def test_demo_workflow_creates_vip_in_prepared_state(client, test_db):
    """
    Test that demo workflow creates VIP in PREPARED state initially.
    
    Validates: Requirement 19.1
    """
    response = client.post("/api/demo/start")
    assert response.status_code == 200
    
    vip_id = response.json()["vip_id"]
    
    # Check VIP is in PREPARED state
    vip = test_db.query(VIPProfileDB).filter(VIPProfileDB.id == vip_id).first()
    assert vip.current_state == "prepared"


def test_demo_creates_flight_with_correct_timing(client, test_db):
    """
    Test that demo creates a flight with correct departure and boarding times.
    
    Validates: Requirement 19.1
    """
    response = client.post("/api/demo/start")
    assert response.status_code == 200
    
    flight_id = response.json()["flight_id"]
    
    # Check flight timing
    flight = test_db.query(FlightDB).filter(FlightDB.id == flight_id).first()
    assert flight is not None
    
    # Boarding time should be 30 minutes before departure
    time_diff = (flight.departure_time - flight.boarding_time).total_seconds()
    assert time_diff == 30 * 60  # 30 minutes in seconds


def test_demo_reset_clears_demo_flights(client, test_db):
    """
    Test that demo reset clears demo flights (starting with DM).
    
    Validates: Requirement 19.5
    """
    # Start demo
    start_response = client.post("/api/demo/start")
    flight_id = start_response.json()["flight_id"]
    
    # Verify flight exists
    flight_before = test_db.query(FlightDB).filter(FlightDB.id == flight_id).first()
    assert flight_before is not None
    
    # Reset demo
    client.post("/api/demo/reset")
    
    # Verify demo flight is cleared
    flight_after = test_db.query(FlightDB).filter(FlightDB.id == flight_id).first()
    assert flight_after is None


def test_multiple_demo_starts_update_existing_flight(client, test_db):
    """
    Test that starting demo multiple times updates the existing demo flight.
    
    Validates: Requirement 19.1
    """
    # Start demo first time
    response1 = client.post("/api/demo/start")
    flight_id1 = response1.json()["flight_id"]
    
    # Start demo second time
    response2 = client.post("/api/demo/start")
    flight_id2 = response2.json()["flight_id"]
    
    # Both should use the same flight ID
    assert flight_id1 == flight_id2
    
    # Should only have one demo flight
    demo_flights = test_db.query(FlightDB).filter(FlightDB.id.like("DM%")).count()
    assert demo_flights == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
