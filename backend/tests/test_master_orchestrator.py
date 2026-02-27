"""
Unit tests for Master Orchestrator.

Tests state machine transitions, event handling, and resource management.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from backend.orchestrator.master_orchestrator import MasterOrchestrator
from backend.orchestrator.event_bus import EventBus
from backend.models.schemas import Event, EventType, VIPState
from backend.database.connection import SessionLocal
from backend.database.models import VIPProfileDB, EscortDB, BuggyDB, LoungeReservationDB
from backend.database import create_tables


@pytest.fixture
def event_bus():
    """Create an event bus instance for testing."""
    return EventBus()


@pytest.fixture
def orchestrator(event_bus):
    """Create a master orchestrator instance for testing."""
    return MasterOrchestrator(event_bus)


@pytest.fixture
def db_session():
    """Create a database session for testing."""
    # Create tables
    create_tables()
    
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_vip(db_session):
    """Create a sample VIP in the database."""
    vip = VIPProfileDB(
        id="test-vip-1",
        name="Test VIP",
        face_embedding=b"test_embedding",
        flight_id="FL123",
        current_state=VIPState.PREPARED.value,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(vip)
    db_session.commit()
    yield vip
    # Cleanup
    db_session.delete(vip)
    db_session.commit()


class TestMasterOrchestratorInitialization:
    """Test Master Orchestrator initialization."""
    
    def test_initialization(self, orchestrator, event_bus):
        """Test that orchestrator initializes correctly."""
        assert orchestrator.event_bus == event_bus
        assert isinstance(orchestrator._active_workflows, dict)
        assert len(orchestrator._active_workflows) == 0
    
    def test_event_subscriptions(self, orchestrator, event_bus):
        """Test that orchestrator subscribes to required events."""
        assert event_bus.get_subscription_count(EventType.VIP_DETECTED) >= 1
        assert event_bus.get_subscription_count(EventType.FLIGHT_DELAY) >= 1
        assert event_bus.get_subscription_count(EventType.BOARDING_ALERT) >= 1


class TestStateTransitions:
    """Test state transition validation and execution."""
    
    def test_valid_state_transitions(self, orchestrator):
        """Test that valid state transitions are defined correctly."""
        assert VIPState.ARRIVED in orchestrator.VALID_TRANSITIONS[VIPState.PREPARED]
        assert VIPState.BUGGY_PICKUP in orchestrator.VALID_TRANSITIONS[VIPState.ARRIVED]
        assert VIPState.CHECKED_IN in orchestrator.VALID_TRANSITIONS[VIPState.BUGGY_PICKUP]
        assert VIPState.SECURITY_CLEARED in orchestrator.VALID_TRANSITIONS[VIPState.CHECKED_IN]
        assert VIPState.LOUNGE_ENTRY in orchestrator.VALID_TRANSITIONS[VIPState.SECURITY_CLEARED]
        assert VIPState.BUGGY_TO_GATE in orchestrator.VALID_TRANSITIONS[VIPState.LOUNGE_ENTRY]
        assert VIPState.BOARDED in orchestrator.VALID_TRANSITIONS[VIPState.BUGGY_TO_GATE]
        assert VIPState.COMPLETED in orchestrator.VALID_TRANSITIONS[VIPState.BOARDED]
        assert orchestrator.VALID_TRANSITIONS[VIPState.COMPLETED] == []
    
    def test_is_valid_transition_success(self, orchestrator):
        """Test valid transition validation."""
        assert orchestrator._is_valid_transition(VIPState.PREPARED, VIPState.ARRIVED) is True
        assert orchestrator._is_valid_transition(VIPState.ARRIVED, VIPState.BUGGY_PICKUP) is True
    
    def test_is_valid_transition_failure(self, orchestrator):
        """Test invalid transition validation."""
        # Skip states
        assert orchestrator._is_valid_transition(VIPState.PREPARED, VIPState.CHECKED_IN) is False
        # Backward transition
        assert orchestrator._is_valid_transition(VIPState.ARRIVED, VIPState.PREPARED) is False
        # From terminal state
        assert orchestrator._is_valid_transition(VIPState.COMPLETED, VIPState.ARRIVED) is False
    
    @pytest.mark.asyncio
    async def test_transition_state_success(self, orchestrator, sample_vip, db_session):
        """Test successful state transition."""
        # Transition from PREPARED to ARRIVED
        success = await orchestrator.transition_state(sample_vip.id, VIPState.ARRIVED)
        
        assert success is True
        
        # Verify database update
        db_session.refresh(sample_vip)
        assert sample_vip.current_state == VIPState.ARRIVED.value
        
        # Verify in-memory tracking
        assert orchestrator._active_workflows[sample_vip.id] == VIPState.ARRIVED
    
    @pytest.mark.asyncio
    async def test_transition_state_invalid(self, orchestrator, sample_vip, db_session):
        """Test rejected invalid state transition."""
        # Try to skip from PREPARED to CHECKED_IN
        success = await orchestrator.transition_state(sample_vip.id, VIPState.CHECKED_IN)
        
        assert success is False
        
        # Verify state unchanged
        db_session.refresh(sample_vip)
        assert sample_vip.current_state == VIPState.PREPARED.value
    
    @pytest.mark.asyncio
    async def test_transition_state_nonexistent_vip(self, orchestrator):
        """Test transition for non-existent VIP."""
        success = await orchestrator.transition_state("nonexistent-vip", VIPState.ARRIVED)
        assert success is False
    
    @pytest.mark.asyncio
    async def test_state_changed_event_emission(self, orchestrator, sample_vip, event_bus):
        """Test that STATE_CHANGED event is emitted after transition."""
        # Track emitted events
        emitted_events = []
        
        async def capture_event(event: Event):
            emitted_events.append(event)
        
        event_bus.subscribe(EventType.STATE_CHANGED, capture_event)
        
        # Perform transition
        await orchestrator.transition_state(sample_vip.id, VIPState.ARRIVED)
        
        # Verify event was emitted
        assert len(emitted_events) == 1
        event = emitted_events[0]
        assert event.event_type == EventType.STATE_CHANGED
        assert event.vip_id == sample_vip.id
        assert event.payload["previous_state"] == VIPState.PREPARED.value
        assert event.payload["new_state"] == VIPState.ARRIVED.value


class TestVIPDetectedHandler:
    """Test VIP_DETECTED event handling."""
    
    @pytest.mark.asyncio
    async def test_handle_vip_detected(self, orchestrator, sample_vip):
        """Test that VIP_DETECTED event transitions VIP to ARRIVED."""
        event = Event(
            event_type=EventType.VIP_DETECTED,
            payload={"confidence": 0.95},
            source_agent="identity_agent",
            vip_id=sample_vip.id
        )
        
        await orchestrator.handle_vip_detected(event)
        
        # Verify VIP transitioned to ARRIVED
        db = SessionLocal()
        try:
            vip = db.query(VIPProfileDB).filter(VIPProfileDB.id == sample_vip.id).first()
            assert vip.current_state == VIPState.ARRIVED.value
        finally:
            db.close()


class TestResourceRelease:
    """Test resource release on workflow completion."""
    
    @pytest.mark.asyncio
    async def test_release_resources_escort(self, orchestrator, sample_vip, db_session):
        """Test that escort is released when VIP completes."""
        # Create assigned escort
        escort = EscortDB(
            id="escort-1",
            name="Test Escort",
            status="assigned",
            assigned_vip_id=sample_vip.id,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(escort)
        db_session.commit()
        
        # Release resources
        await orchestrator._release_resources(sample_vip.id)
        
        # Verify escort released
        db_session.refresh(escort)
        assert escort.status == "available"
        assert escort.assigned_vip_id is None
        
        # Cleanup
        db_session.delete(escort)
        db_session.commit()
    
    @pytest.mark.asyncio
    async def test_release_resources_buggy(self, orchestrator, sample_vip, db_session):
        """Test that buggy is released when VIP completes."""
        # Create assigned buggy
        buggy = BuggyDB(
            id="buggy-1",
            battery_level=80,
            status="assigned",
            assigned_vip_id=sample_vip.id,
            current_location="en_route_destination",
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(buggy)
        db_session.commit()
        
        # Release resources
        await orchestrator._release_resources(sample_vip.id)
        
        # Verify buggy released
        db_session.refresh(buggy)
        assert buggy.status == "available"
        assert buggy.assigned_vip_id is None
        assert buggy.current_location == "idle"
        
        # Cleanup
        db_session.delete(buggy)
        db_session.commit()
    
    @pytest.mark.asyncio
    async def test_release_resources_lounge(self, orchestrator, sample_vip, db_session):
        """Test that lounge reservation is released when VIP completes."""
        # Create active lounge reservation
        reservation = LoungeReservationDB(
            id="reservation-1",
            vip_id=sample_vip.id,
            reservation_time=datetime.now(timezone.utc),
            entry_time=datetime.now(timezone.utc),
            duration_minutes=90,
            status="active"
        )
        db_session.add(reservation)
        db_session.commit()
        
        # Release resources
        await orchestrator._release_resources(sample_vip.id)
        
        # Verify reservation completed
        db_session.refresh(reservation)
        assert reservation.status == "completed"
        assert reservation.exit_time is not None
        
        # Cleanup
        db_session.delete(reservation)
        db_session.commit()
    
    @pytest.mark.asyncio
    async def test_transition_to_completed_releases_resources(self, orchestrator, sample_vip, db_session):
        """Test that transitioning to COMPLETED automatically releases resources."""
        # Set VIP to BOARDED state
        sample_vip.current_state = VIPState.BOARDED.value
        db_session.commit()
        
        # Create assigned resources
        escort = EscortDB(
            id="escort-1",
            name="Test Escort",
            status="assigned",
            assigned_vip_id=sample_vip.id,
            created_at=datetime.now(timezone.utc)
        )
        db_session.add(escort)
        db_session.commit()
        
        # Transition to COMPLETED
        await orchestrator.transition_state(sample_vip.id, VIPState.COMPLETED)
        
        # Verify resources released
        db_session.refresh(escort)
        assert escort.status == "available"
        
        # Verify removed from active workflows
        assert sample_vip.id not in orchestrator._active_workflows
        
        # Cleanup
        db_session.delete(escort)
        db_session.commit()


class TestFlightDelayHandler:
    """Test flight delay handling."""
    
    @pytest.mark.asyncio
    async def test_handle_flight_delay_extends_lounge(self, orchestrator, sample_vip, db_session):
        """Test that flight delay extends lounge reservation."""
        # Set VIP to LOUNGE_ENTRY state
        sample_vip.current_state = VIPState.LOUNGE_ENTRY.value
        db_session.commit()
        
        # Create lounge reservation
        reservation = LoungeReservationDB(
            id="reservation-1",
            vip_id=sample_vip.id,
            reservation_time=datetime.now(timezone.utc),
            entry_time=datetime.now(timezone.utc),
            duration_minutes=90,
            status="active"
        )
        db_session.add(reservation)
        db_session.commit()
        
        # Create flight delay event
        event = Event(
            event_type=EventType.FLIGHT_DELAY,
            payload={
                "flight_id": sample_vip.flight_id,
                "new_departure_time": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
                "delay_minutes": 30
            },
            source_agent="flight_intelligence_agent"
        )
        
        # Handle delay
        await orchestrator.handle_flight_delay(event)
        
        # Verify lounge reservation extended
        db_session.refresh(reservation)
        assert reservation.duration_minutes == 120  # 90 + 30
        
        # Cleanup
        db_session.delete(reservation)
        db_session.commit()
    
    @pytest.mark.asyncio
    async def test_handle_flight_delay_multiple_vips(self, orchestrator, sample_vip, db_session):
        """Test that flight delay affects all VIPs on the flight."""
        # Create second VIP on same flight
        vip2 = VIPProfileDB(
            id="test-vip-2",
            name="Test VIP 2",
            face_embedding=b"test_embedding_2",
            flight_id=sample_vip.flight_id,
            current_state=VIPState.LOUNGE_ENTRY.value,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(vip2)
        
        # Set first VIP to LOUNGE_ENTRY
        sample_vip.current_state = VIPState.LOUNGE_ENTRY.value
        db_session.commit()
        
        # Create reservations for both VIPs
        res1 = LoungeReservationDB(
            id="reservation-1",
            vip_id=sample_vip.id,
            reservation_time=datetime.now(timezone.utc),
            entry_time=datetime.now(timezone.utc),
            duration_minutes=90,
            status="active"
        )
        res2 = LoungeReservationDB(
            id="reservation-2",
            vip_id=vip2.id,
            reservation_time=datetime.now(timezone.utc),
            entry_time=datetime.now(timezone.utc),
            duration_minutes=90,
            status="active"
        )
        db_session.add_all([res1, res2])
        db_session.commit()
        
        # Create flight delay event
        event = Event(
            event_type=EventType.FLIGHT_DELAY,
            payload={
                "flight_id": sample_vip.flight_id,
                "new_departure_time": (datetime.now(timezone.utc) + timedelta(minutes=45)).isoformat(),
                "delay_minutes": 45
            },
            source_agent="flight_intelligence_agent"
        )
        
        # Handle delay
        await orchestrator.handle_flight_delay(event)
        
        # Verify both reservations extended
        db_session.refresh(res1)
        db_session.refresh(res2)
        assert res1.duration_minutes == 135  # 90 + 45
        assert res2.duration_minutes == 135  # 90 + 45
        
        # Cleanup
        db_session.delete(res1)
        db_session.delete(res2)
        db_session.delete(vip2)
        db_session.commit()


class TestBoardingAlertHandler:
    """Test boarding alert handling."""
    
    @pytest.mark.asyncio
    async def test_handle_boarding_alert(self, orchestrator, sample_vip, db_session):
        """Test that boarding alert transitions VIP to BUGGY_TO_GATE."""
        # Set VIP to LOUNGE_ENTRY state
        sample_vip.current_state = VIPState.LOUNGE_ENTRY.value
        db_session.commit()
        
        # Create boarding alert event
        event = Event(
            event_type=EventType.BOARDING_ALERT,
            payload={
                "flight_id": sample_vip.flight_id,
                "vip_ids": [sample_vip.id]
            },
            source_agent="flight_intelligence_agent"
        )
        
        # Handle boarding alert
        await orchestrator.handle_boarding_alert(event)
        
        # Verify VIP transitioned to BUGGY_TO_GATE
        db_session.refresh(sample_vip)
        assert sample_vip.current_state == VIPState.BUGGY_TO_GATE.value
    
    @pytest.mark.asyncio
    async def test_handle_boarding_alert_wrong_state(self, orchestrator, sample_vip, db_session):
        """Test that boarding alert doesn't transition VIP in wrong state."""
        # Keep VIP in PREPARED state
        assert sample_vip.current_state == VIPState.PREPARED.value
        
        # Create boarding alert event
        event = Event(
            event_type=EventType.BOARDING_ALERT,
            payload={
                "flight_id": sample_vip.flight_id,
                "vip_ids": [sample_vip.id]
            },
            source_agent="flight_intelligence_agent"
        )
        
        # Handle boarding alert
        await orchestrator.handle_boarding_alert(event)
        
        # Verify VIP state unchanged
        db_session.refresh(sample_vip)
        assert sample_vip.current_state == VIPState.PREPARED.value


class TestWorkflowRecovery:
    """Test workflow recovery on system restart."""
    
    @pytest.mark.asyncio
    async def test_recover_workflows(self, orchestrator, sample_vip, db_session):
        """Test that active workflows are recovered from database."""
        # Set VIP to ARRIVED state
        sample_vip.current_state = VIPState.ARRIVED.value
        db_session.commit()
        
        # Recover workflows
        await orchestrator.recover_workflows()
        
        # Verify VIP added to active workflows
        assert sample_vip.id in orchestrator._active_workflows
        assert orchestrator._active_workflows[sample_vip.id] == VIPState.ARRIVED
    
    @pytest.mark.asyncio
    async def test_recover_workflows_excludes_completed(self, orchestrator, db_session):
        """Test that completed VIPs are not recovered."""
        # Create completed VIP
        completed_vip = VIPProfileDB(
            id="completed-vip",
            name="Completed VIP",
            face_embedding=b"test_embedding",
            flight_id="FL999",
            current_state=VIPState.COMPLETED.value,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add(completed_vip)
        db_session.commit()
        
        # Recover workflows
        await orchestrator.recover_workflows()
        
        # Verify completed VIP not in active workflows
        assert completed_vip.id not in orchestrator._active_workflows
        
        # Cleanup
        db_session.delete(completed_vip)
        db_session.commit()
    
    @pytest.mark.asyncio
    async def test_recover_multiple_workflows(self, orchestrator, sample_vip, db_session):
        """Test recovery of multiple active workflows."""
        # Create additional VIPs in different states
        vip2 = VIPProfileDB(
            id="test-vip-2",
            name="Test VIP 2",
            face_embedding=b"test_embedding_2",
            flight_id="FL456",
            current_state=VIPState.CHECKED_IN.value,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        vip3 = VIPProfileDB(
            id="test-vip-3",
            name="Test VIP 3",
            face_embedding=b"test_embedding_3",
            flight_id="FL789",
            current_state=VIPState.LOUNGE_ENTRY.value,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db_session.add_all([vip2, vip3])
        db_session.commit()
        
        # Recover workflows
        await orchestrator.recover_workflows()
        
        # Verify all active VIPs recovered
        assert len(orchestrator._active_workflows) >= 3
        assert sample_vip.id in orchestrator._active_workflows
        assert vip2.id in orchestrator._active_workflows
        assert vip3.id in orchestrator._active_workflows
        
        # Cleanup
        db_session.delete(vip2)
        db_session.delete(vip3)
        db_session.commit()


class TestGetActiveWorkflows:
    """Test getting active workflows."""
    
    def test_get_active_workflows_empty(self, orchestrator):
        """Test getting active workflows when none exist."""
        workflows = orchestrator.get_active_workflows()
        assert isinstance(workflows, dict)
        assert len(workflows) == 0
    
    @pytest.mark.asyncio
    async def test_get_active_workflows_with_data(self, orchestrator, sample_vip):
        """Test getting active workflows with data."""
        # Transition VIP to create active workflow
        await orchestrator.transition_state(sample_vip.id, VIPState.ARRIVED)
        
        # Get workflows
        workflows = orchestrator.get_active_workflows()
        
        assert len(workflows) >= 1
        assert sample_vip.id in workflows
        assert workflows[sample_vip.id] == VIPState.ARRIVED
    
    def test_get_active_workflows_returns_copy(self, orchestrator):
        """Test that get_active_workflows returns a copy, not reference."""
        workflows1 = orchestrator.get_active_workflows()
        workflows2 = orchestrator.get_active_workflows()
        
        # Modify one copy
        workflows1["test"] = VIPState.ARRIVED
        
        # Verify other copy unchanged
        assert "test" not in workflows2
        assert "test" not in orchestrator._active_workflows
