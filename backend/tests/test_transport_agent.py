"""
Unit tests for Transport Agent.

Tests buggy allocation, dispatch, battery management, and trip simulation.
"""

import asyncio
import pytest
import sys
from datetime import datetime, timezone

# Import directly to avoid triggering identity_agent imports
sys.path.insert(0, 'backend')

# Import transport agent directly without going through __init__
from backend.agents.transport_agent import TransportAgent
from backend.orchestrator.event_bus import EventBus
from backend.models.schemas import Event, EventType, BuggyStatus, VIPState
from backend.database.connection import SessionLocal, engine
from backend.database.models import Base, BuggyDB


@pytest.fixture(scope="function")
def setup_database():
    """Create fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def event_bus():
    """Create event bus instance."""
    return EventBus()


@pytest.fixture
def transport_agent(event_bus):
    """Create transport agent instance."""
    return TransportAgent(event_bus)


@pytest.fixture
def sample_buggies(setup_database):
    """Create sample buggies in database."""
    db = SessionLocal()
    try:
        buggies = [
            BuggyDB(
                id="buggy-1",
                battery_level=80,
                status=BuggyStatus.AVAILABLE.value,
                assigned_vip_id=None,
                current_location="idle"
            ),
            BuggyDB(
                id="buggy-2",
                battery_level=50,
                status=BuggyStatus.AVAILABLE.value,
                assigned_vip_id=None,
                current_location="idle"
            ),
            BuggyDB(
                id="buggy-3",
                battery_level=15,
                status=BuggyStatus.CHARGING.value,
                assigned_vip_id=None,
                current_location="idle"
            ),
            BuggyDB(
                id="buggy-4",
                battery_level=25,
                status=BuggyStatus.ASSIGNED.value,
                assigned_vip_id="vip-999",
                current_location="en_route_pickup"
            ),
        ]
        
        for buggy in buggies:
            db.add(buggy)
        
        db.commit()
        
        return buggies
        
    finally:
        db.close()


@pytest.mark.asyncio
async def test_find_available_buggy(transport_agent, sample_buggies):
    """Test finding an available buggy with battery > 20%."""
    buggy_id = await transport_agent.find_available_buggy()
    
    assert buggy_id is not None
    
    # Verify battery level and status
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.id == buggy_id).first()
        assert buggy is not None
        assert buggy.battery_level > 20
        assert buggy.status == BuggyStatus.AVAILABLE.value
    finally:
        db.close()


@pytest.mark.asyncio
async def test_find_available_buggy_none_available(transport_agent, setup_database):
    """Test finding buggy when none are available with sufficient battery."""
    # Create only low-battery or assigned buggies
    db = SessionLocal()
    try:
        buggies = [
            BuggyDB(
                id="buggy-1",
                battery_level=15,
                status=BuggyStatus.CHARGING.value,
                assigned_vip_id=None,
                current_location="idle"
            ),
            BuggyDB(
                id="buggy-2",
                battery_level=50,
                status=BuggyStatus.ASSIGNED.value,
                assigned_vip_id="vip-123",
                current_location="en_route_pickup"
            ),
        ]
        for buggy in buggies:
            db.add(buggy)
        db.commit()
    finally:
        db.close()
    
    buggy_id = await transport_agent.find_available_buggy()
    assert buggy_id is None



@pytest.mark.asyncio
async def test_dispatch_buggy(transport_agent, sample_buggies, event_bus):
    """Test dispatching a buggy to a VIP."""
    # Track emitted events
    emitted_events = []
    
    async def capture_event(event: Event):
        emitted_events.append(event)
    
    event_bus.subscribe(EventType.BUGGY_DISPATCHED, capture_event)
    
    # Dispatch buggy
    await transport_agent.dispatch_buggy("buggy-1", "vip-123", "lounge")
    
    # Verify database update
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.id == "buggy-1").first()
        assert buggy is not None
        assert buggy.status == BuggyStatus.ASSIGNED.value
        assert buggy.assigned_vip_id == "vip-123"
        assert buggy.current_location == "en_route_pickup"
    finally:
        db.close()
    
    # Verify event emission
    assert len(emitted_events) == 1
    event = emitted_events[0]
    assert event.event_type == EventType.BUGGY_DISPATCHED
    assert event.payload["buggy_id"] == "buggy-1"
    assert event.payload["vip_id"] == "vip-123"
    assert event.payload["destination"] == "lounge"
    assert event.vip_id == "vip-123"


@pytest.mark.asyncio
async def test_simulate_trip_battery_depletion(transport_agent, sample_buggies):
    """Test that trip simulation depletes battery by 5%."""
    # Get initial battery level
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.id == "buggy-1").first()
        initial_battery = buggy.battery_level
    finally:
        db.close()
    
    # Simulate a very short trip (0 minutes for testing)
    await transport_agent.simulate_trip("buggy-1", 0)
    
    # Verify battery depleted by 5%
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.id == "buggy-1").first()
        assert buggy.battery_level == initial_battery - 5
        assert buggy.current_location == "idle"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_simulate_trip_low_battery_marks_charging(transport_agent, setup_database):
    """Test that buggy with battery <= 20% after trip is marked as charging."""
    # Create buggy with 25% battery
    db = SessionLocal()
    try:
        buggy = BuggyDB(
            id="buggy-1",
            battery_level=25,
            status=BuggyStatus.ASSIGNED.value,
            assigned_vip_id="vip-123",
            current_location="en_route_destination"
        )
        db.add(buggy)
        db.commit()
    finally:
        db.close()
    
    # Simulate trip (will deplete to 20%)
    await transport_agent.simulate_trip("buggy-1", 0)
    
    # Verify buggy is marked as charging
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.id == "buggy-1").first()
        assert buggy.battery_level == 20
        assert buggy.status == BuggyStatus.CHARGING.value
        assert buggy.assigned_vip_id is None
    finally:
        db.close()



@pytest.mark.asyncio
async def test_release_buggy_with_sufficient_battery(transport_agent, sample_buggies):
    """Test releasing a buggy with battery > 20%."""
    # Assign buggy first
    await transport_agent.dispatch_buggy("buggy-1", "vip-123", "lounge")
    
    # Release buggy
    await transport_agent.release_buggy("buggy-1")
    
    # Verify buggy is available
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.id == "buggy-1").first()
        assert buggy.status == BuggyStatus.AVAILABLE.value
        assert buggy.assigned_vip_id is None
        assert buggy.current_location == "idle"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_release_buggy_with_low_battery(transport_agent, setup_database):
    """Test releasing a buggy with battery <= 20% marks it as charging."""
    # Create buggy with low battery
    db = SessionLocal()
    try:
        buggy = BuggyDB(
            id="buggy-1",
            battery_level=15,
            status=BuggyStatus.ASSIGNED.value,
            assigned_vip_id="vip-123",
            current_location="en_route_destination"
        )
        db.add(buggy)
        db.commit()
    finally:
        db.close()
    
    # Release buggy
    await transport_agent.release_buggy("buggy-1")
    
    # Verify buggy is marked as charging
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.id == "buggy-1").first()
        assert buggy.status == BuggyStatus.CHARGING.value
        assert buggy.assigned_vip_id is None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_release_buggy_by_vip(transport_agent, sample_buggies):
    """Test releasing a buggy by VIP ID."""
    # Assign buggy to VIP
    await transport_agent.dispatch_buggy("buggy-1", "vip-123", "lounge")
    
    # Release by VIP ID
    await transport_agent.release_buggy_by_vip("vip-123")
    
    # Verify buggy is released
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.id == "buggy-1").first()
        assert buggy.status == BuggyStatus.AVAILABLE.value
        assert buggy.assigned_vip_id is None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_allocate_buggy_to_vip(transport_agent, sample_buggies, event_bus):
    """Test allocating a buggy to a VIP."""
    # Track emitted events
    emitted_events = []
    
    async def capture_event(event: Event):
        emitted_events.append(event)
    
    event_bus.subscribe(EventType.BUGGY_DISPATCHED, capture_event)
    
    # Allocate buggy
    await transport_agent.allocate_buggy_to_vip("vip-123")
    
    # Verify buggy was dispatched
    assert len(emitted_events) == 1
    assert emitted_events[0].payload["vip_id"] == "vip-123"
    
    # Verify database
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.assigned_vip_id == "vip-123").first()
        assert buggy is not None
        assert buggy.status == BuggyStatus.ASSIGNED.value
    finally:
        db.close()



@pytest.mark.asyncio
async def test_handle_vip_detected(transport_agent, sample_buggies, event_bus):
    """Test handling VIP_DETECTED event."""
    # Track assignments
    assignments = []
    
    async def capture_assignment(event: Event):
        assignments.append(event.payload["vip_id"])
    
    event_bus.subscribe(EventType.BUGGY_DISPATCHED, capture_assignment)
    
    # Emit VIP_DETECTED event
    vip_detected_event = Event(
        event_type=EventType.VIP_DETECTED,
        payload={"vip_id": "vip-123", "confidence": 0.95},
        source_agent="identity_agent",
        vip_id="vip-123"
    )
    
    await event_bus.publish(vip_detected_event)
    
    # Give time for async processing
    await asyncio.sleep(0.1)
    
    # Verify buggy was assigned
    assert "vip-123" in assignments


@pytest.mark.asyncio
async def test_handle_state_changed_security_cleared(transport_agent, sample_buggies, event_bus):
    """Test handling STATE_CHANGED event when VIP clears security."""
    # First allocate a buggy
    await transport_agent.allocate_buggy_to_vip("vip-123")
    
    # Get the assigned buggy
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.assigned_vip_id == "vip-123").first()
        buggy_id = buggy.id
        initial_battery = buggy.battery_level
    finally:
        db.close()
    
    # Emit STATE_CHANGED event with SECURITY_CLEARED state
    state_changed_event = Event(
        event_type=EventType.STATE_CHANGED,
        payload={
            "vip_id": "vip-123",
            "previous_state": VIPState.CHECKED_IN.value,
            "new_state": VIPState.SECURITY_CLEARED.value
        },
        source_agent="master_orchestrator",
        vip_id="vip-123"
    )
    
    await event_bus.publish(state_changed_event)
    
    # Give time for async processing (trip simulation)
    await asyncio.sleep(0.2)
    
    # Verify buggy completed trip (battery depleted)
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.id == buggy_id).first()
        assert buggy.battery_level == initial_battery - 5
        assert buggy.current_location == "idle"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_handle_state_changed_boarded(transport_agent, sample_buggies, event_bus):
    """Test handling STATE_CHANGED event when VIP boards."""
    # Assign buggy to VIP
    await transport_agent.dispatch_buggy("buggy-1", "vip-123", "gate")
    
    # Verify buggy is assigned
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.id == "buggy-1").first()
        assert buggy.status == BuggyStatus.ASSIGNED.value
    finally:
        db.close()
    
    # Emit STATE_CHANGED event with BOARDED state
    state_changed_event = Event(
        event_type=EventType.STATE_CHANGED,
        payload={
            "vip_id": "vip-123",
            "previous_state": VIPState.BUGGY_TO_GATE.value,
            "new_state": VIPState.BOARDED.value
        },
        source_agent="master_orchestrator",
        vip_id="vip-123"
    )
    
    await event_bus.publish(state_changed_event)
    
    # Give time for async processing
    await asyncio.sleep(0.1)
    
    # Verify buggy was released
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.id == "buggy-1").first()
        assert buggy.status == BuggyStatus.AVAILABLE.value
        assert buggy.assigned_vip_id is None
    finally:
        db.close()



@pytest.mark.asyncio
async def test_handle_boarding_alert(transport_agent, sample_buggies, event_bus):
    """Test handling BOARDING_ALERT event."""
    # First allocate a buggy
    await transport_agent.allocate_buggy_to_vip("vip-123")
    
    # Get the assigned buggy
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.assigned_vip_id == "vip-123").first()
        buggy_id = buggy.id
        initial_battery = buggy.battery_level
    finally:
        db.close()
    
    # Emit BOARDING_ALERT event
    boarding_alert_event = Event(
        event_type=EventType.BOARDING_ALERT,
        payload={
            "vip_id": "vip-123",
            "flight_id": "AA123",
            "gate": "A5"
        },
        source_agent="flight_intelligence_agent",
        vip_id="vip-123"
    )
    
    await event_bus.publish(boarding_alert_event)
    
    # Give time for async processing (trip simulation)
    await asyncio.sleep(0.2)
    
    # Verify buggy completed trip to gate (battery depleted)
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.id == buggy_id).first()
        assert buggy.battery_level == initial_battery - 5
        assert buggy.current_location == "idle"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_dispatch_buggy_to_gate_destination(transport_agent, sample_buggies):
    """Test dispatching buggy to gate updates location correctly."""
    # Assign buggy to VIP
    await transport_agent.dispatch_buggy("buggy-1", "vip-123", "gate")
    
    # Verify location is set to en_route_destination for gate
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.id == "buggy-1").first()
        assert buggy.current_location == "en_route_destination"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_battery_never_goes_negative(transport_agent, setup_database):
    """Test that battery level never goes below 0."""
    # Create buggy with 3% battery
    db = SessionLocal()
    try:
        buggy = BuggyDB(
            id="buggy-1",
            battery_level=3,
            status=BuggyStatus.ASSIGNED.value,
            assigned_vip_id="vip-123",
            current_location="en_route_destination"
        )
        db.add(buggy)
        db.commit()
    finally:
        db.close()
    
    # Simulate trip (would deplete to -2% without protection)
    await transport_agent.simulate_trip("buggy-1", 0)
    
    # Verify battery is 0, not negative
    db = SessionLocal()
    try:
        buggy = db.query(BuggyDB).filter(BuggyDB.id == "buggy-1").first()
        assert buggy.battery_level == 0
        assert buggy.battery_level >= 0
    finally:
        db.close()
