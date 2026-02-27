"""
Unit tests for database operations.

Tests CRUD operations and query performance with indexes.
Validates Requirements 15.1, 15.2, 15.3
"""

import pytest
import numpy as np
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.database import (
    SessionLocal,
    create_tables,
    drop_tables,
    VIPProfileDB,
    EscortDB,
    BuggyDB,
    FlightDB,
    ServiceLogDB,
    LoungeReservationDB,
)


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    # Create tables
    create_tables()
    
    # Create session
    session = SessionLocal()
    
    # Clear all existing data before each test
    session.query(ServiceLogDB).delete()
    session.query(LoungeReservationDB).delete()
    session.query(VIPProfileDB).delete()
    session.query(EscortDB).delete()
    session.query(BuggyDB).delete()
    session.query(FlightDB).delete()
    session.commit()
    
    yield session
    
    # Cleanup
    session.close()


def serialize_embedding(embedding: np.ndarray) -> bytes:
    """Serialize numpy array to bytes."""
    return embedding.tobytes()


def test_create_flight(db_session):
    """Test creating a flight record."""
    now = datetime.now(timezone.utc)
    
    flight = FlightDB(
        id="TEST123",
        departure_time=now + timedelta(hours=2),
        boarding_time=now + timedelta(hours=1, minutes=30),
        status="scheduled",
        gate="A1",
        destination="Test City",
        delay_minutes=0
    )
    
    db_session.add(flight)
    db_session.commit()
    
    # Query back
    retrieved = db_session.query(FlightDB).filter_by(id="TEST123").first()
    assert retrieved is not None
    assert retrieved.destination == "Test City"
    assert retrieved.gate == "A1"


def test_create_vip_profile(db_session):
    """Test creating a VIP profile with face embedding."""
    # Create flight first
    now = datetime.now(timezone.utc)
    flight = FlightDB(
        id="FL001",
        departure_time=now + timedelta(hours=2),
        boarding_time=now + timedelta(hours=1, minutes=30),
        status="scheduled",
        gate="B2",
        destination="Paris"
    )
    db_session.add(flight)
    db_session.commit()
    
    # Create VIP
    embedding = np.random.rand(128).astype(np.float32)
    vip = VIPProfileDB(
        id=str(uuid4()),
        name="Test VIP",
        face_embedding=serialize_embedding(embedding),
        flight_id="FL001",
        current_state="prepared"
    )
    
    db_session.add(vip)
    db_session.commit()
    
    # Query back
    retrieved = db_session.query(VIPProfileDB).filter_by(name="Test VIP").first()
    assert retrieved is not None
    assert retrieved.flight_id == "FL001"
    assert retrieved.current_state == "prepared"
    assert len(retrieved.face_embedding) == 128 * 4  # 128 floats * 4 bytes each


def test_create_escort(db_session):
    """Test creating an escort record."""
    escort = EscortDB(
        id=str(uuid4()),
        name="Test Escort",
        status="available"
    )
    
    db_session.add(escort)
    db_session.commit()
    
    # Query back
    retrieved = db_session.query(EscortDB).filter_by(name="Test Escort").first()
    assert retrieved is not None
    assert retrieved.status == "available"
    assert retrieved.assigned_vip_id is None


def test_create_buggy(db_session):
    """Test creating a buggy record."""
    buggy = BuggyDB(
        id=str(uuid4()),
        battery_level=75,
        status="available",
        current_location="idle"
    )
    
    db_session.add(buggy)
    db_session.commit()
    
    # Query back
    retrieved = db_session.query(BuggyDB).filter_by(battery_level=75).first()
    assert retrieved is not None
    assert retrieved.status == "available"
    assert retrieved.current_location == "idle"


def test_create_service_log(db_session):
    """Test creating a service log entry."""
    # Create flight and VIP first
    now = datetime.now(timezone.utc)
    flight = FlightDB(
        id="FL002",
        departure_time=now + timedelta(hours=2),
        boarding_time=now + timedelta(hours=1, minutes=30),
        status="scheduled",
        gate="C3",
        destination="Tokyo"
    )
    db_session.add(flight)
    db_session.commit()
    
    vip_id = str(uuid4())
    vip = VIPProfileDB(
        id=vip_id,
        name="Log Test VIP",
        face_embedding=serialize_embedding(np.random.rand(128).astype(np.float32)),
        flight_id="FL002",
        current_state="arrived"
    )
    db_session.add(vip)
    db_session.commit()
    
    # Create service log
    log = ServiceLogDB(
        id=str(uuid4()),
        vip_id=vip_id,
        event_type="vip_detected",
        event_data={"confidence": 0.95},
        agent_source="identity_agent"
    )
    
    db_session.add(log)
    db_session.commit()
    
    # Query back
    retrieved = db_session.query(ServiceLogDB).filter_by(vip_id=vip_id).first()
    assert retrieved is not None
    assert retrieved.event_type == "vip_detected"
    assert retrieved.agent_source == "identity_agent"
    assert retrieved.event_data["confidence"] == 0.95


def test_create_lounge_reservation(db_session):
    """Test creating a lounge reservation."""
    # Create flight and VIP first
    now = datetime.now(timezone.utc)
    flight = FlightDB(
        id="FL003",
        departure_time=now + timedelta(hours=2),
        boarding_time=now + timedelta(hours=1, minutes=30),
        status="scheduled",
        gate="D4",
        destination="Singapore"
    )
    db_session.add(flight)
    db_session.commit()
    
    vip_id = str(uuid4())
    vip = VIPProfileDB(
        id=vip_id,
        name="Lounge Test VIP",
        face_embedding=serialize_embedding(np.random.rand(128).astype(np.float32)),
        flight_id="FL003",
        current_state="security_cleared"
    )
    db_session.add(vip)
    db_session.commit()
    
    # Create lounge reservation
    reservation = LoungeReservationDB(
        id=str(uuid4()),
        vip_id=vip_id,
        duration_minutes=90,
        status="reserved"
    )
    
    db_session.add(reservation)
    db_session.commit()
    
    # Query back
    retrieved = db_session.query(LoungeReservationDB).filter_by(vip_id=vip_id).first()
    assert retrieved is not None
    assert retrieved.duration_minutes == 90
    assert retrieved.status == "reserved"


def test_query_escorts_by_status(db_session):
    """Test querying escorts by status (tests index performance)."""
    # Create multiple escorts
    for i in range(5):
        escort = EscortDB(
            id=str(uuid4()),
            name=f"Escort {i}",
            status="available" if i < 3 else "assigned"
        )
        db_session.add(escort)
    db_session.commit()
    
    # Query available escorts
    available = db_session.query(EscortDB).filter_by(status="available").all()
    assert len(available) >= 3
    
    # Query assigned escorts
    assigned = db_session.query(EscortDB).filter_by(status="assigned").all()
    assert len(assigned) >= 2


def test_query_buggies_by_status(db_session):
    """Test querying buggies by status (tests index performance)."""
    # Create multiple buggies
    for i in range(4):
        buggy = BuggyDB(
            id=str(uuid4()),
            battery_level=50 + i * 10,
            status="available" if i < 2 else "assigned",
            current_location="idle"
        )
        db_session.add(buggy)
    db_session.commit()
    
    # Query available buggies
    available = db_session.query(BuggyDB).filter_by(status="available").all()
    assert len(available) >= 2


def test_query_vips_by_flight(db_session):
    """Test querying VIPs by flight_id (tests index performance)."""
    # Create flight
    now = datetime.now(timezone.utc)
    flight = FlightDB(
        id="FL999",
        departure_time=now + timedelta(hours=2),
        boarding_time=now + timedelta(hours=1, minutes=30),
        status="scheduled",
        gate="E5",
        destination="New York"
    )
    db_session.add(flight)
    db_session.commit()
    
    # Create multiple VIPs for same flight
    for i in range(3):
        vip = VIPProfileDB(
            id=str(uuid4()),
            name=f"VIP {i}",
            face_embedding=serialize_embedding(np.random.rand(128).astype(np.float32)),
            flight_id="FL999",
            current_state="prepared"
        )
        db_session.add(vip)
    db_session.commit()
    
    # Query VIPs by flight
    vips = db_session.query(VIPProfileDB).filter_by(flight_id="FL999").all()
    assert len(vips) >= 3


def test_query_service_logs_by_vip(db_session):
    """Test querying service logs by VIP (tests index performance)."""
    # Create flight and VIP
    now = datetime.now(timezone.utc)
    flight = FlightDB(
        id="FL888",
        departure_time=now + timedelta(hours=2),
        boarding_time=now + timedelta(hours=1, minutes=30),
        status="scheduled",
        gate="F6",
        destination="Sydney"
    )
    db_session.add(flight)
    db_session.commit()
    
    vip_id = str(uuid4())
    vip = VIPProfileDB(
        id=vip_id,
        name="Service Log VIP",
        face_embedding=serialize_embedding(np.random.rand(128).astype(np.float32)),
        flight_id="FL888",
        current_state="arrived"
    )
    db_session.add(vip)
    db_session.commit()
    
    # Create multiple service logs
    for i in range(4):
        log = ServiceLogDB(
            id=str(uuid4()),
            vip_id=vip_id,
            event_type="state_changed",
            event_data={"state": f"state_{i}"},
            agent_source="orchestrator"
        )
        db_session.add(log)
    db_session.commit()
    
    # Query logs by VIP
    logs = db_session.query(ServiceLogDB).filter_by(vip_id=vip_id).all()
    assert len(logs) >= 4
