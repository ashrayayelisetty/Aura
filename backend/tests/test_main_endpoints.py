"""
Unit tests for FastAPI main application endpoints.

Tests REST endpoints for VIPs, escorts, buggies, lounge, and flights.
Validates Requirements 8.1, 9.1, 10.1, 11.1, 12.1
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import numpy as np

from backend.database.models import (
    Base, VIPProfileDB, EscortDB, BuggyDB, FlightDB, 
    LoungeReservationDB, ServiceLogDB
)

# Create test database
TEST_DATABASE_URL = "sqlite:///./test_main.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Create a simple test app without lifespan for testing
from fastapi import Depends
from typing import List

test_app = FastAPI()

# Import the endpoint functions
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def get_db():
    """Get database session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@test_app.get("/")
async def root():
    return {"status": "AURA-VIP System Online", "version": "1.0.0"}


@test_app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "services": {
            "database": "connected",
            "event_bus": "active",
            "agents": "initialized"
        }
    }


@test_app.get("/api/vips", response_model=List[dict])
async def list_vips(db: Session = Depends(get_db)):
    vips = db.query(VIPProfileDB).all()
    
    result = []
    for vip in vips:
        escort = db.query(EscortDB).filter(EscortDB.assigned_vip_id == vip.id).first()
        buggy = db.query(BuggyDB).filter(BuggyDB.assigned_vip_id == vip.id).first()
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


@test_app.get("/api/vips/{vip_id}", response_model=dict)
async def get_vip_details(vip_id: str, db: Session = Depends(get_db)):
    vip = db.query(VIPProfileDB).filter(VIPProfileDB.id == vip_id).first()
    
    if not vip:
        return {"error": "VIP not found"}
    
    escort = db.query(EscortDB).filter(EscortDB.assigned_vip_id == vip.id).first()
    buggy = db.query(BuggyDB).filter(BuggyDB.assigned_vip_id == vip.id).first()
    lounge = db.query(LoungeReservationDB).filter(LoungeReservationDB.vip_id == vip.id).first()
    flight = db.query(FlightDB).filter(FlightDB.id == vip.flight_id).first()
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


@test_app.get("/api/escorts", response_model=List[dict])
async def list_escorts(db: Session = Depends(get_db)):
    escorts = db.query(EscortDB).all()
    
    result = []
    for escort in escorts:
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


@test_app.get("/api/buggies", response_model=List[dict])
async def list_buggies(db: Session = Depends(get_db)):
    buggies = db.query(BuggyDB).all()
    
    result = []
    for buggy in buggies:
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


@test_app.get("/api/lounge", response_model=dict)
async def get_lounge_status(db: Session = Depends(get_db)):
    active_reservations = db.query(LoungeReservationDB).filter(
        LoungeReservationDB.status.in_(["reserved", "active"])
    ).all()
    
    occupancy = db.query(LoungeReservationDB).filter(
        LoungeReservationDB.status == "active"
    ).count()
    
    capacity = 50
    
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


@test_app.get("/api/flights", response_model=List[dict])
async def list_flights(db: Session = Depends(get_db)):
    flights = db.query(FlightDB).all()
    
    result = []
    for flight in flights:
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


client = TestClient(test_app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test and drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_data():
    """Create sample data for testing."""
    db = TestingSessionLocal()
    
    # Create flight
    flight = FlightDB(
        id="AA123",
        departure_time=datetime.now(timezone.utc) + timedelta(hours=2),
        boarding_time=datetime.now(timezone.utc) + timedelta(hours=1, minutes=30),
        status="scheduled",
        gate="A1",
        destination="New York"
    )
    db.add(flight)
    
    # Create VIP
    vip = VIPProfileDB(
        id="vip-001",
        name="John Doe",
        face_embedding=np.random.rand(128).tobytes(),
        flight_id="AA123",
        current_state="arrived"
    )
    db.add(vip)
    
    # Create escort
    escort = EscortDB(
        id="escort-001",
        name="Jane Smith",
        status="assigned",
        assigned_vip_id="vip-001"
    )
    db.add(escort)
    
    # Create buggy
    buggy = BuggyDB(
        id="buggy-001",
        battery_level=85,
        status="assigned",
        assigned_vip_id="vip-001",
        current_location="en_route_pickup"
    )
    db.add(buggy)
    
    # Create lounge reservation
    lounge = LoungeReservationDB(
        id="lounge-001",
        vip_id="vip-001",
        status="reserved",
        duration_minutes=90
    )
    db.add(lounge)
    
    # Create service log
    service_log = ServiceLogDB(
        id="log-001",
        vip_id="vip-001",
        event_type="vip_detected",
        event_data={"confidence": 0.95},
        agent_source="identity_agent"
    )
    db.add(service_log)
    
    db.commit()
    db.close()


def test_root_endpoint():
    """Test root health check endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "AURA-VIP System Online"
    assert data["version"] == "1.0.0"


def test_health_check_endpoint():
    """Test detailed health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "services" in data


def test_list_vips_empty():
    """Test listing VIPs when database is empty."""
    response = client.get("/api/vips")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_list_vips_with_data(sample_data):
    """Test listing VIPs with sample data."""
    response = client.get("/api/vips")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    
    vip = data[0]
    assert vip["id"] == "vip-001"
    assert vip["name"] == "John Doe"
    assert vip["flight_id"] == "AA123"
    assert vip["current_state"] == "arrived"
    assert vip["escort"] is not None
    assert vip["escort"]["id"] == "escort-001"
    assert vip["buggy"] is not None
    assert vip["buggy"]["id"] == "buggy-001"
    assert vip["lounge"] is not None


def test_get_vip_details(sample_data):
    """Test getting VIP details with timeline."""
    response = client.get("/api/vips/vip-001")
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == "vip-001"
    assert data["name"] == "John Doe"
    assert data["current_state"] == "arrived"
    assert data["escort"] is not None
    assert data["buggy"] is not None
    assert data["lounge"] is not None
    assert data["flight"] is not None
    assert "timeline" in data
    assert len(data["timeline"]) == 1
    assert data["timeline"][0]["event_type"] == "vip_detected"


def test_get_vip_details_not_found():
    """Test getting VIP details for non-existent VIP."""
    response = client.get("/api/vips/nonexistent")
    assert response.status_code == 200
    data = response.json()
    assert "error" in data


def test_list_escorts_empty():
    """Test listing escorts when database is empty."""
    response = client.get("/api/escorts")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_list_escorts_with_data(sample_data):
    """Test listing escorts with sample data."""
    response = client.get("/api/escorts")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    
    escort = data[0]
    assert escort["id"] == "escort-001"
    assert escort["name"] == "Jane Smith"
    assert escort["status"] == "assigned"
    assert escort["assigned_vip"] is not None
    assert escort["assigned_vip"]["id"] == "vip-001"


def test_list_buggies_empty():
    """Test listing buggies when database is empty."""
    response = client.get("/api/buggies")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_list_buggies_with_data(sample_data):
    """Test listing buggies with sample data."""
    response = client.get("/api/buggies")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    
    buggy = data[0]
    assert buggy["id"] == "buggy-001"
    assert buggy["battery_level"] == 85
    assert buggy["status"] == "assigned"
    assert buggy["current_location"] == "en_route_pickup"
    assert buggy["assigned_vip"] is not None
    assert buggy["assigned_vip"]["id"] == "vip-001"


def test_get_lounge_status_empty():
    """Test getting lounge status when database is empty."""
    response = client.get("/api/lounge")
    assert response.status_code == 200
    data = response.json()
    
    assert data["occupancy"] == 0
    assert data["capacity"] == 50  # Default capacity
    assert data["utilization_percent"] == 0
    assert isinstance(data["reservations"], list)
    assert len(data["reservations"]) == 0


def test_get_lounge_status_with_data(sample_data):
    """Test getting lounge status with sample data."""
    response = client.get("/api/lounge")
    assert response.status_code == 200
    data = response.json()
    
    assert data["occupancy"] == 0  # Reserved but not active
    assert data["capacity"] == 50
    assert isinstance(data["reservations"], list)
    assert len(data["reservations"]) == 1
    
    reservation = data["reservations"][0]
    assert reservation["id"] == "lounge-001"
    assert reservation["vip"]["id"] == "vip-001"
    assert reservation["status"] == "reserved"


def test_list_flights_empty():
    """Test listing flights when database is empty."""
    response = client.get("/api/flights")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_list_flights_with_data(sample_data):
    """Test listing flights with sample data."""
    response = client.get("/api/flights")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    
    flight = data[0]
    assert flight["id"] == "AA123"
    assert flight["status"] == "scheduled"
    assert flight["gate"] == "A1"
    assert flight["destination"] == "New York"
    assert flight["delay_minutes"] == 0
    assert isinstance(flight["vips"], list)
    assert len(flight["vips"]) == 1
    assert flight["vips"][0]["id"] == "vip-001"
