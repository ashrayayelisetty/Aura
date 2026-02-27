"""
Unit tests for Escort Agent.

Tests escort assignment logic, queueing, and resource release.
"""

import asyncio
import pytest
import sys
from datetime import datetime, timezone

# Import directly to avoid triggering identity_agent imports
sys.path.insert(0, 'backend')

# Import escort agent directly without going through __init__
from backend.agents.escort_agent import EscortAgent
from backend.orchestrator.event_bus import EventBus
from backend.models.schemas import Event, EventType, EscortStatus, VIPState
from backend.database.connection import SessionLocal, engine
from backend.database.models import Base, EscortDB


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
def escort_agent(event_bus):
    """Create escort agent instance."""
    return EscortAgent(event_bus)


@pytest.fixture
def sample_escorts(setup_database):
    """Create sample escorts in database."""
    db = SessionLocal()
    try:
        escorts = [
            EscortDB(
                id="escort-1",
                name="Alice Smith",
                status=EscortStatus.AVAILABLE.value,
                assigned_vip_id=None
            ),
            EscortDB(
                id="escort-2",
                name="Bob Johnson",
                status=EscortStatus.AVAILABLE.value,
                assigned_vip_id=None
            ),
            EscortDB(
                id="escort-3",
                name="Carol Williams",
                status=EscortStatus.ASSIGNED.value,
                assigned_vip_id="vip-999"
            ),
        ]
        
        for escort in escorts:
            db.add(escort)
        
        db.commit()
        
        return escorts
        
    finally:
        db.close()


@pytest.mark.asyncio
async def test_find_available_escort(escort_agent, sample_escorts):
    """Test finding an available escort from the pool."""
    escort_id = await escort_agent.find_available_escort()
    
    assert escort_id is not None
    assert escort_id in ["escort-1", "escort-2"]


@pytest.mark.asyncio
async def test_find_available_escort_none_available(escort_agent, setup_database):
    """Test finding escort when none are available."""
    # Create only assigned escorts
    db = SessionLocal()
    try:
        escort = EscortDB(
            id="escort-1",
            name="Alice Smith",
            status=EscortStatus.ASSIGNED.value,
            assigned_vip_id="vip-123"
        )
        db.add(escort)
        db.commit()
    finally:
        db.close()
    
    escort_id = await escort_agent.find_available_escort()
    assert escort_id is None


@pytest.mark.asyncio
async def test_assign_escort(escort_agent, sample_escorts, event_bus):
    """Test assigning an escort to a VIP."""
    # Track emitted events
    emitted_events = []
    
    async def capture_event(event: Event):
        emitted_events.append(event)
    
    event_bus.subscribe(EventType.ESCORT_ASSIGNED, capture_event)
    
    # Assign escort
    await escort_agent.assign_escort("escort-1", "vip-123")
    
    # Verify database update
    db = SessionLocal()
    try:
        escort = db.query(EscortDB).filter(EscortDB.id == "escort-1").first()
        assert escort is not None
        assert escort.status == EscortStatus.ASSIGNED.value
        assert escort.assigned_vip_id == "vip-123"
    finally:
        db.close()
    
    # Verify event emission
    assert len(emitted_events) == 1
    event = emitted_events[0]
    assert event.event_type == EventType.ESCORT_ASSIGNED
    assert event.payload["escort_id"] == "escort-1"
    assert event.payload["vip_id"] == "vip-123"
    assert event.vip_id == "vip-123"


@pytest.mark.asyncio
async def test_release_escort(escort_agent, sample_escorts):
    """Test releasing an escort back to available status."""
    # First assign an escort
    await escort_agent.assign_escort("escort-1", "vip-123")
    
    # Then release it
    await escort_agent.release_escort("escort-1")
    
    # Verify database update
    db = SessionLocal()
    try:
        escort = db.query(EscortDB).filter(EscortDB.id == "escort-1").first()
        assert escort is not None
        assert escort.status == EscortStatus.AVAILABLE.value
        assert escort.assigned_vip_id is None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_release_escort_by_vip(escort_agent, sample_escorts):
    """Test releasing an escort by VIP ID."""
    # Assign escort to VIP
    await escort_agent.assign_escort("escort-1", "vip-123")
    
    # Release by VIP ID
    await escort_agent.release_escort_by_vip("vip-123")
    
    # Verify escort is released
    db = SessionLocal()
    try:
        escort = db.query(EscortDB).filter(EscortDB.id == "escort-1").first()
        assert escort.status == EscortStatus.AVAILABLE.value
        assert escort.assigned_vip_id is None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_request_queueing(escort_agent, setup_database):
    """Test queueing requests when no escorts are available."""
    # Create one escort and assign it
    db = SessionLocal()
    try:
        escort = EscortDB(
            id="escort-1",
            name="Alice Smith",
            status=EscortStatus.ASSIGNED.value,
            assigned_vip_id="vip-100"
        )
        db.add(escort)
        db.commit()
    finally:
        db.close()
    
    # Try to assign to another VIP (should queue)
    await escort_agent.assign_escort_to_vip("vip-200")
    
    # Verify request is queued
    assert len(escort_agent._request_queue) == 1
    assert escort_agent._request_queue[0] == "vip-200"


@pytest.mark.asyncio
async def test_queue_processing_fifo(escort_agent, sample_escorts, event_bus):
    """Test that queued requests are processed in FIFO order."""
    # Track assignments
    assignments = []
    
    async def capture_assignment(event: Event):
        assignments.append(event.payload["vip_id"])
    
    event_bus.subscribe(EventType.ESCORT_ASSIGNED, capture_assignment)
    
    # Assign all available escorts
    await escort_agent.assign_escort("escort-1", "vip-100")
    await escort_agent.assign_escort("escort-2", "vip-101")
    
    # Queue three more requests
    await escort_agent.assign_escort_to_vip("vip-200")
    await escort_agent.assign_escort_to_vip("vip-201")
    await escort_agent.assign_escort_to_vip("vip-202")
    
    # Verify queue
    assert len(escort_agent._request_queue) == 3
    
    # Release one escort (should process first queued request)
    await escort_agent.release_escort("escort-1")
    
    # Verify first queued request was processed
    assert len(escort_agent._request_queue) == 2
    assert "vip-200" in assignments
    
    # Release another escort
    await escort_agent.release_escort("escort-2")
    
    # Verify second queued request was processed
    assert len(escort_agent._request_queue) == 1
    assert "vip-201" in assignments


@pytest.mark.asyncio
async def test_handle_vip_detected(escort_agent, sample_escorts, event_bus):
    """Test handling VIP_DETECTED event."""
    # Track assignments
    assignments = []
    
    async def capture_assignment(event: Event):
        assignments.append(event.payload["vip_id"])
    
    event_bus.subscribe(EventType.ESCORT_ASSIGNED, capture_assignment)
    
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
    
    # Verify escort was assigned
    assert "vip-123" in assignments


@pytest.mark.asyncio
async def test_handle_state_changed_completed(escort_agent, sample_escorts, event_bus):
    """Test handling STATE_CHANGED event when VIP completes journey."""
    # Assign escort to VIP
    await escort_agent.assign_escort("escort-1", "vip-123")
    
    # Verify escort is assigned
    db = SessionLocal()
    try:
        escort = db.query(EscortDB).filter(EscortDB.id == "escort-1").first()
        assert escort.status == EscortStatus.ASSIGNED.value
    finally:
        db.close()
    
    # Emit STATE_CHANGED event with COMPLETED state
    state_changed_event = Event(
        event_type=EventType.STATE_CHANGED,
        payload={
            "vip_id": "vip-123",
            "previous_state": VIPState.BOARDED.value,
            "new_state": VIPState.COMPLETED.value
        },
        source_agent="master_orchestrator",
        vip_id="vip-123"
    )
    
    await event_bus.publish(state_changed_event)
    
    # Give time for async processing
    await asyncio.sleep(0.1)
    
    # Verify escort was released
    db = SessionLocal()
    try:
        escort = db.query(EscortDB).filter(EscortDB.id == "escort-1").first()
        assert escort.status == EscortStatus.AVAILABLE.value
        assert escort.assigned_vip_id is None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_handle_state_changed_non_completed(escort_agent, sample_escorts, event_bus):
    """Test that non-COMPLETED state changes don't release escorts."""
    # Assign escort to VIP
    await escort_agent.assign_escort("escort-1", "vip-123")
    
    # Emit STATE_CHANGED event with non-COMPLETED state
    state_changed_event = Event(
        event_type=EventType.STATE_CHANGED,
        payload={
            "vip_id": "vip-123",
            "previous_state": VIPState.ARRIVED.value,
            "new_state": VIPState.BUGGY_PICKUP.value
        },
        source_agent="master_orchestrator",
        vip_id="vip-123"
    )
    
    await event_bus.publish(state_changed_event)
    
    # Give time for async processing
    await asyncio.sleep(0.1)
    
    # Verify escort is still assigned
    db = SessionLocal()
    try:
        escort = db.query(EscortDB).filter(EscortDB.id == "escort-1").first()
        assert escort.status == EscortStatus.ASSIGNED.value
        assert escort.assigned_vip_id == "vip-123"
    finally:
        db.close()
