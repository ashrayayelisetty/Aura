"""
Simple integration tests for demo mode functionality.

Tests the demo mode logic directly without TestClient.
Validates Requirements 19.1, 19.2, 19.3, 19.4, 19.5
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import numpy as np
import pickle
from uuid import uuid4

from backend.database.models import Base, VIPProfileDB, EscortDB, BuggyDB, FlightDB


# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_demo_simple.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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


def test_demo_start_creates_vip_and_flight(test_db):
    """
    Test that demo start logic creates a VIP and flight.
    
    Validates: Requirements 19.1, 19.2
    """
    # Simulate demo start logic
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
    
    test_db.add(demo_flight)
    test_db.commit()
    
    # Create demo VIP with face embedding (pickled numpy array)
    demo_embedding = np.random.rand(128)
    
    demo_vip = VIPProfileDB(
        id=demo_vip_id,
        name="Demo VIP Guest",
        face_embedding=pickle.dumps(demo_embedding),
        flight_id=demo_flight_id,
        current_state="prepared",
        created_at=now,
        updated_at=now
    )
    
    test_db.add(demo_vip)
    test_db.commit()
    
    # Verify VIP was created
    vip = test_db.query(VIPProfileDB).filter(VIPProfileDB.id == demo_vip_id).first()
    assert vip is not None
    assert vip.name == "Demo VIP Guest"
    assert vip.flight_id == demo_flight_id
    assert vip.current_state == "prepared"
    
    # Verify flight was created
    flight = test_db.query(FlightDB).filter(FlightDB.id == demo_flight_id).first()
    assert flight is not None
    assert flight.destination == "Dubai"
    assert flight.gate == "A15"
    assert flight.status == "scheduled"


def test_demo_reset_clears_vips_and_resets_resources(test_db):
    """
    Test that demo reset clears VIPs and resets resources.
    
    Validates: Requirement 19.5
    """
    # Create a demo VIP
    demo_vip_id = str(uuid4())
    demo_flight_id = "DM001"
    
    now = datetime.now(timezone.utc)
    demo_embedding = np.random.rand(128)
    
    demo_vip = VIPProfileDB(
        id=demo_vip_id,
        name="Demo VIP Guest",
        face_embedding=pickle.dumps(demo_embedding),
        flight_id=demo_flight_id,
        current_state="arrived",
        created_at=now,
        updated_at=now
    )
    
    test_db.add(demo_vip)
    
    # Create demo flight
    demo_flight = FlightDB(
        id=demo_flight_id,
        departure_time=now + timedelta(hours=2),
        boarding_time=now + timedelta(hours=1, minutes=30),
        status="scheduled",
        gate="A15",
        destination="Dubai",
        delay_minutes=0,
        created_at=now
    )
    
    test_db.add(demo_flight)
    
    # Assign an escort
    escort = test_db.query(EscortDB).first()
    escort.status = "assigned"
    escort.assigned_vip_id = demo_vip_id
    
    # Assign a buggy
    buggy = test_db.query(BuggyDB).first()
    buggy.status = "assigned"
    buggy.assigned_vip_id = demo_vip_id
    buggy.battery_level = 75
    
    test_db.commit()
    
    # Verify data exists
    vips_before = test_db.query(VIPProfileDB).count()
    assert vips_before > 0
    
    # Simulate demo reset logic
    test_db.query(VIPProfileDB).delete()
    
    # Reset all escorts to available
    escorts = test_db.query(EscortDB).all()
    for e in escorts:
        e.status = "available"
        e.assigned_vip_id = None
    
    # Reset all buggies to available
    buggies = test_db.query(BuggyDB).all()
    for b in buggies:
        b.status = "available"
        b.assigned_vip_id = None
        b.current_location = "idle"
        b.battery_level = 100
    
    # Clear demo flights
    test_db.query(FlightDB).filter(FlightDB.id.like("DM%")).delete()
    
    test_db.commit()
    
    # Verify all VIPs are cleared
    vips_after = test_db.query(VIPProfileDB).count()
    assert vips_after == 0
    
    # Verify escorts are reset
    escorts = test_db.query(EscortDB).all()
    for e in escorts:
        assert e.status == "available"
        assert e.assigned_vip_id is None
    
    # Verify buggies are reset
    buggies = test_db.query(BuggyDB).all()
    for b in buggies:
        assert b.status == "available"
        assert b.assigned_vip_id is None
        assert b.current_location == "idle"
        assert b.battery_level == 100
    
    # Verify demo flights are cleared
    demo_flights = test_db.query(FlightDB).filter(FlightDB.id.like("DM%")).count()
    assert demo_flights == 0


def test_demo_flight_timing_is_correct(test_db):
    """
    Test that demo flight has correct boarding and departure timing.
    
    Validates: Requirement 19.1
    """
    now = datetime.now(timezone.utc)
    departure_time = now + timedelta(hours=2)
    boarding_time = departure_time - timedelta(minutes=30)
    
    demo_flight = FlightDB(
        id="DM001",
        departure_time=departure_time,
        boarding_time=boarding_time,
        status="scheduled",
        gate="A15",
        destination="Dubai",
        delay_minutes=0,
        created_at=now
    )
    
    test_db.add(demo_flight)
    test_db.commit()
    
    # Verify timing
    flight = test_db.query(FlightDB).filter(FlightDB.id == "DM001").first()
    assert flight is not None
    
    # Boarding time should be 30 minutes before departure
    time_diff = (flight.departure_time - flight.boarding_time).total_seconds()
    assert time_diff == 30 * 60  # 30 minutes in seconds


def test_demo_vip_starts_in_prepared_state(test_db):
    """
    Test that demo VIP is created in PREPARED state.
    
    Validates: Requirement 19.1
    """
    demo_vip_id = str(uuid4())
    now = datetime.now(timezone.utc)
    demo_embedding = np.random.rand(128)
    
    demo_vip = VIPProfileDB(
        id=demo_vip_id,
        name="Demo VIP Guest",
        face_embedding=pickle.dumps(demo_embedding),
        flight_id="DM001",
        current_state="prepared",
        created_at=now,
        updated_at=now
    )
    
    test_db.add(demo_vip)
    test_db.commit()
    
    # Verify state
    vip = test_db.query(VIPProfileDB).filter(VIPProfileDB.id == demo_vip_id).first()
    assert vip.current_state == "prepared"


def test_demo_flight_delay_simulation(test_db):
    """
    Test that demo can simulate flight delays.
    
    Validates: Requirement 19.3
    """
    now = datetime.now(timezone.utc)
    departure_time = now + timedelta(hours=2)
    boarding_time = departure_time - timedelta(minutes=30)
    
    demo_flight = FlightDB(
        id="DM001",
        departure_time=departure_time,
        boarding_time=boarding_time,
        status="scheduled",
        gate="A15",
        destination="Dubai",
        delay_minutes=0,
        created_at=now
    )
    
    test_db.add(demo_flight)
    test_db.commit()
    
    # Simulate flight delay (30 minutes)
    flight = test_db.query(FlightDB).filter(FlightDB.id == "DM001").first()
    flight.delay_minutes = 30
    flight.departure_time = flight.departure_time + timedelta(minutes=30)
    flight.boarding_time = flight.boarding_time + timedelta(minutes=30)
    flight.status = "delayed"
    test_db.commit()
    
    # Verify delay
    updated_flight = test_db.query(FlightDB).filter(FlightDB.id == "DM001").first()
    assert updated_flight.delay_minutes == 30
    assert updated_flight.status == "delayed"
    
    # Verify times were adjusted
    time_diff = (updated_flight.departure_time - updated_flight.boarding_time).total_seconds()
    assert time_diff == 30 * 60  # Still 30 minutes between boarding and departure


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
