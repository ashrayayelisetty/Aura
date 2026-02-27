"""
Unit tests for Baggage Agent.

Tests priority baggage tagging, routing simulation, and priority adjustment.
"""

import asyncio
import pytest
import sys
from datetime import datetime, timezone

# Import directly to avoid triggering identity_agent imports
sys.path.insert(0, 'backend')

from backend.agents.baggage_agent import BaggageAgent
from backend.orchestrator.event_bus import EventBus
from backend.models.schemas import Event, EventType, VIPState
from backend.database.connection import SessionLocal, engine
from backend.database.models import Base, VIPProfileDB


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
def baggage_agent(event_bus):
    """Create baggage agent instance."""
    return BaggageAgent(event_bus)


@pytest.fixture
def sample_vip(setup_database):
    """Create sample VIP in database."""
    db = SessionLocal()
    try:
        vip = VIPProfileDB(
            id="vip-123",
            name="John Doe",
            face_embedding=b'\x00' * 1024,  # Dummy embedding
            flight_id="AA100",
            current_state=VIPState.CHECKED_IN.value
        )
        db.add(vip)
        db.commit()
        return vip
    finally:
        db.close()


@pytest.mark.asyncio
async def test_generate_priority_tag(baggage_agent, sample_vip, event_bus):
    """Test generating priority baggage tag for VIP."""
    # Track emitted events
    emitted_events = []
    
    async def capture_event(event: Event):
        emitted_events.append(event)
    
    event_bus.subscribe(EventType.BAGGAGE_PRIORITY_TAGGED, capture_event)
    
    # Generate priority tag
    await baggage_agent.generate_priority_tag("vip-123")
    
    # Give time for async processing
    await asyncio.sleep(0.1)
    
    # Verify event emission
    assert len(emitted_events) == 1
    event = emitted_events[0]
    assert event.event_type == EventType.BAGGAGE_PRIORITY_TAGGED
    assert event.payload["vip_id"] == "vip-123"
    assert event.payload["flight_id"] == "AA100"
    assert event.payload["priority"] == 10
    assert "tag_id" in event.payload
    assert event.vip_id == "vip-123"
    
    # Verify internal state (status will be "routing" since simulation starts immediately)
    assert baggage_agent._baggage_status["vip-123"] in ["tagged", "routing"]
    assert baggage_agent._baggage_priority["vip-123"] == 10


@pytest.mark.asyncio
async def test_track_loading_status(baggage_agent, sample_vip):
    """Test tracking baggage loading status."""
    # Initial status should be not_tagged
    status = await baggage_agent.track_loading_status("vip-123")
    assert status == "not_tagged"
    
    # Manually set status to tagged (without starting simulation)
    baggage_agent._baggage_status["vip-123"] = "tagged"
    baggage_agent._baggage_priority["vip-123"] = 10
    
    # Status should be tagged
    status = await baggage_agent.track_loading_status("vip-123")
    assert status == "tagged"


@pytest.mark.asyncio
async def test_simulate_baggage_routing(baggage_agent, sample_vip, event_bus):
    """Test baggage routing simulation."""
    # Track state changes
    state_changes = []
    
    async def capture_state_change(event: Event):
        if event.payload.get("baggage_status") == "loaded":
            state_changes.append(event)
    
    event_bus.subscribe(EventType.STATE_CHANGED, capture_state_change)
    
    # Set initial status
    baggage_agent._baggage_status["vip-123"] = "tagged"
    
    # Start routing simulation (use very short time for testing)
    # We'll mock the sleep to avoid waiting
    original_sleep = asyncio.sleep
    
    async def mock_sleep(seconds):
        await original_sleep(0.01)  # Sleep for 10ms instead
    
    asyncio.sleep = mock_sleep
    
    try:
        await baggage_agent.simulate_baggage_routing("vip-123", "AA100")
        
        # Verify status changed to loaded
        assert baggage_agent._baggage_status["vip-123"] == "loaded"
        
        # Verify event was emitted
        assert len(state_changes) == 1
        event = state_changes[0]
        assert event.payload["baggage_status"] == "loaded"
        assert event.payload["vip_id"] == "vip-123"
        assert event.payload["flight_id"] == "AA100"
        assert "completion_time" in event.payload
        
    finally:
        asyncio.sleep = original_sleep


@pytest.mark.asyncio
async def test_adjust_priority_for_delay_significant(baggage_agent, sample_vip):
    """Test adjusting priority for significant flight delay (>60 min)."""
    # Set initial priority
    baggage_agent._baggage_priority["vip-123"] = 10
    baggage_agent._baggage_status["vip-123"] = "tagged"
    
    # Adjust for 90 minute delay
    await baggage_agent.adjust_priority_for_delay("vip-123", 90)
    
    # Priority should be reduced (10 - 3 = 7)
    assert baggage_agent._baggage_priority["vip-123"] == 7


@pytest.mark.asyncio
async def test_adjust_priority_for_delay_moderate(baggage_agent, sample_vip):
    """Test adjusting priority for moderate flight delay (30-60 min)."""
    # Set initial priority
    baggage_agent._baggage_priority["vip-123"] = 10
    baggage_agent._baggage_status["vip-123"] = "tagged"
    
    # Adjust for 45 minute delay
    await baggage_agent.adjust_priority_for_delay("vip-123", 45)
    
    # Priority should be reduced (10 - 2 = 8)
    assert baggage_agent._baggage_priority["vip-123"] == 8


@pytest.mark.asyncio
async def test_adjust_priority_for_delay_short(baggage_agent, sample_vip):
    """Test adjusting priority for short flight delay (<30 min)."""
    # Set initial priority
    baggage_agent._baggage_priority["vip-123"] = 10
    baggage_agent._baggage_status["vip-123"] = "tagged"
    
    # Adjust for 20 minute delay
    await baggage_agent.adjust_priority_for_delay("vip-123", 20)
    
    # Priority should be reduced slightly (10 - 1 = 9)
    assert baggage_agent._baggage_priority["vip-123"] == 9


@pytest.mark.asyncio
async def test_adjust_priority_already_loaded(baggage_agent, sample_vip):
    """Test that priority adjustment is skipped if baggage already loaded."""
    # Set initial priority and status
    baggage_agent._baggage_priority["vip-123"] = 10
    baggage_agent._baggage_status["vip-123"] = "loaded"
    
    # Try to adjust priority
    await baggage_agent.adjust_priority_for_delay("vip-123", 60)
    
    # Priority should remain unchanged
    assert baggage_agent._baggage_priority["vip-123"] == 10


@pytest.mark.asyncio
async def test_adjust_priority_minimum_threshold(baggage_agent, sample_vip):
    """Test that priority doesn't go below minimum threshold."""
    # Set low initial priority
    baggage_agent._baggage_priority["vip-123"] = 6
    baggage_agent._baggage_status["vip-123"] = "tagged"
    
    # Adjust for significant delay
    await baggage_agent.adjust_priority_for_delay("vip-123", 90)
    
    # Priority should not go below 5
    assert baggage_agent._baggage_priority["vip-123"] == 5


@pytest.mark.asyncio
async def test_handle_state_changed_checked_in(baggage_agent, sample_vip, event_bus):
    """Test handling STATE_CHANGED event when VIP checks in."""
    # Track emitted events
    emitted_events = []
    
    async def capture_event(event: Event):
        emitted_events.append(event)
    
    event_bus.subscribe(EventType.BAGGAGE_PRIORITY_TAGGED, capture_event)
    
    # Emit STATE_CHANGED event with CHECKED_IN state
    state_changed_event = Event(
        event_type=EventType.STATE_CHANGED,
        payload={
            "vip_id": "vip-123",
            "previous_state": VIPState.BUGGY_PICKUP.value,
            "new_state": VIPState.CHECKED_IN.value
        },
        source_agent="master_orchestrator",
        vip_id="vip-123"
    )
    
    await event_bus.publish(state_changed_event)
    
    # Give time for async processing
    await asyncio.sleep(0.1)
    
    # Verify priority tag was generated
    assert len(emitted_events) == 1
    assert emitted_events[0].payload["vip_id"] == "vip-123"


@pytest.mark.asyncio
async def test_handle_state_changed_non_checked_in(baggage_agent, sample_vip, event_bus):
    """Test that non-CHECKED_IN state changes don't generate tags."""
    # Track emitted events
    emitted_events = []
    
    async def capture_event(event: Event):
        emitted_events.append(event)
    
    event_bus.subscribe(EventType.BAGGAGE_PRIORITY_TAGGED, capture_event)
    
    # Emit STATE_CHANGED event with non-CHECKED_IN state
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
    
    # Verify no tag was generated
    assert len(emitted_events) == 0


@pytest.mark.asyncio
async def test_handle_flight_delay_with_vip_id(baggage_agent, sample_vip, event_bus):
    """Test handling FLIGHT_DELAY event with VIP ID."""
    # Set initial priority
    baggage_agent._baggage_priority["vip-123"] = 10
    baggage_agent._baggage_status["vip-123"] = "tagged"
    
    # Emit FLIGHT_DELAY event
    flight_delay_event = Event(
        event_type=EventType.FLIGHT_DELAY,
        payload={
            "vip_id": "vip-123",
            "flight_id": "AA100",
            "delay_minutes": 60,
            "new_departure_time": datetime.now(timezone.utc).isoformat()
        },
        source_agent="flight_intelligence_agent",
        vip_id="vip-123"
    )
    
    await event_bus.publish(flight_delay_event)
    
    # Give time for async processing
    await asyncio.sleep(0.1)
    
    # Verify priority was adjusted
    assert baggage_agent._baggage_priority["vip-123"] < 10


@pytest.mark.asyncio
async def test_handle_flight_delay_with_flight_id(baggage_agent, setup_database, event_bus):
    """Test handling FLIGHT_DELAY event with flight ID (affects all VIPs on flight)."""
    # Create multiple VIPs on same flight
    db = SessionLocal()
    try:
        vips = [
            VIPProfileDB(
                id="vip-1",
                name="VIP One",
                face_embedding=b'\x00' * 1024,
                flight_id="AA100",
                current_state=VIPState.CHECKED_IN.value
            ),
            VIPProfileDB(
                id="vip-2",
                name="VIP Two",
                face_embedding=b'\x00' * 1024,
                flight_id="AA100",
                current_state=VIPState.CHECKED_IN.value
            ),
        ]
        for vip in vips:
            db.add(vip)
        db.commit()
    finally:
        db.close()
    
    # Set initial priorities
    baggage_agent._baggage_priority["vip-1"] = 10
    baggage_agent._baggage_status["vip-1"] = "tagged"
    baggage_agent._baggage_priority["vip-2"] = 10
    baggage_agent._baggage_status["vip-2"] = "tagged"
    
    # Emit FLIGHT_DELAY event with flight_id
    flight_delay_event = Event(
        event_type=EventType.FLIGHT_DELAY,
        payload={
            "flight_id": "AA100",
            "delay_minutes": 45,
            "new_departure_time": datetime.now(timezone.utc).isoformat()
        },
        source_agent="flight_intelligence_agent"
    )
    
    await event_bus.publish(flight_delay_event)
    
    # Give time for async processing
    await asyncio.sleep(0.2)
    
    # Verify both VIPs had priority adjusted
    assert baggage_agent._baggage_priority["vip-1"] < 10
    assert baggage_agent._baggage_priority["vip-2"] < 10


@pytest.mark.asyncio
async def test_get_vips_on_flight(baggage_agent, setup_database):
    """Test retrieving all VIPs on a specific flight."""
    # Create VIPs on different flights
    db = SessionLocal()
    try:
        vips = [
            VIPProfileDB(
                id="vip-1",
                name="VIP One",
                face_embedding=b'\x00' * 1024,
                flight_id="AA100",
                current_state=VIPState.ARRIVED.value
            ),
            VIPProfileDB(
                id="vip-2",
                name="VIP Two",
                face_embedding=b'\x00' * 1024,
                flight_id="AA100",
                current_state=VIPState.ARRIVED.value
            ),
            VIPProfileDB(
                id="vip-3",
                name="VIP Three",
                face_embedding=b'\x00' * 1024,
                flight_id="BA200",
                current_state=VIPState.ARRIVED.value
            ),
        ]
        for vip in vips:
            db.add(vip)
        db.commit()
    finally:
        db.close()
    
    # Get VIPs on AA100
    vip_ids = await baggage_agent._get_vips_on_flight("AA100")
    
    # Verify correct VIPs returned
    assert len(vip_ids) == 2
    assert "vip-1" in vip_ids
    assert "vip-2" in vip_ids
    assert "vip-3" not in vip_ids
