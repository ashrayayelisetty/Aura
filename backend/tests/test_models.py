"""
Unit tests for Pydantic models.

Tests validation logic for all data models and enums.
Validates Requirements 15.1, 15.2, 20.1
"""

from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError

from backend.models import (
    VIPProfile,
    Escort,
    Buggy,
    Flight,
    ServiceLog,
    LoungeReservation,
    Event,
    VIPState,
    EscortStatus,
    BuggyStatus,
    FlightStatus,
    ReservationStatus,
    EventType,
)


class TestVIPProfile:
    """Test VIPProfile model validation."""
    
    def test_valid_vip_profile(self):
        """Test creating a valid VIP profile."""
        profile = VIPProfile(
            name="John Doe",
            face_embedding=[0.1] * 128,
            flight_id="AA123"
        )
        assert profile.name == "John Doe"
        assert len(profile.face_embedding) == 128
        assert profile.current_state == VIPState.PREPARED
        assert profile.id is not None
    
    def test_invalid_embedding_length(self):
        """Test that face embedding must be exactly 128 dimensions."""
        with pytest.raises(ValidationError):
            VIPProfile(
                name="John Doe",
                face_embedding=[0.1] * 64,  # Wrong length
                flight_id="AA123"
            )
    
    def test_empty_name(self):
        """Test that name cannot be empty."""
        with pytest.raises(ValidationError):
            VIPProfile(
                name="   ",
                face_embedding=[0.1] * 128,
                flight_id="AA123"
            )
    
    def test_name_whitespace_trimmed(self):
        """Test that name whitespace is trimmed."""
        profile = VIPProfile(
            name="  John Doe  ",
            face_embedding=[0.1] * 128,
            flight_id="AA123"
        )
        assert profile.name == "John Doe"


class TestEscort:
    """Test Escort model validation."""
    
    def test_valid_available_escort(self):
        """Test creating an available escort."""
        escort = Escort(name="Jane Smith", status=EscortStatus.AVAILABLE)
        assert escort.name == "Jane Smith"
        assert escort.status == EscortStatus.AVAILABLE
        assert escort.assigned_vip_id is None
    
    def test_valid_assigned_escort(self):
        """Test creating an assigned escort."""
        escort = Escort(
            name="Jane Smith",
            status=EscortStatus.ASSIGNED,
            assigned_vip_id="vip-123"
        )
        assert escort.status == EscortStatus.ASSIGNED
        assert escort.assigned_vip_id == "vip-123"
    
    def test_assigned_without_vip_id(self):
        """Test that assigned escort must have VIP ID."""
        with pytest.raises(ValidationError):
            Escort(name="Jane Smith", status=EscortStatus.ASSIGNED)
    
    def test_available_with_vip_id(self):
        """Test that available escort cannot have VIP ID."""
        with pytest.raises(ValidationError):
            Escort(
                name="Jane Smith",
                status=EscortStatus.AVAILABLE,
                assigned_vip_id="vip-123"
            )


class TestBuggy:
    """Test Buggy model validation."""
    
    def test_valid_available_buggy(self):
        """Test creating an available buggy."""
        buggy = Buggy(battery_level=80, status=BuggyStatus.AVAILABLE)
        assert buggy.battery_level == 80
        assert buggy.status == BuggyStatus.AVAILABLE
        assert buggy.current_location == "idle"
    
    def test_valid_assigned_buggy(self):
        """Test creating an assigned buggy."""
        buggy = Buggy(
            battery_level=50,
            status=BuggyStatus.ASSIGNED,
            assigned_vip_id="vip-123",
            current_location="en_route_pickup"
        )
        assert buggy.status == BuggyStatus.ASSIGNED
        assert buggy.assigned_vip_id == "vip-123"
    
    def test_battery_level_bounds(self):
        """Test that battery level must be between 0 and 100."""
        with pytest.raises(ValidationError):
            Buggy(battery_level=101, status=BuggyStatus.AVAILABLE)
        
        with pytest.raises(ValidationError):
            Buggy(battery_level=-1, status=BuggyStatus.AVAILABLE)
    
    def test_assigned_low_battery(self):
        """Test that buggy with low battery cannot be assigned."""
        with pytest.raises(ValidationError):
            Buggy(
                battery_level=20,
                status=BuggyStatus.ASSIGNED,
                assigned_vip_id="vip-123"
            )
    
    def test_invalid_location(self):
        """Test that location must be one of allowed values."""
        with pytest.raises(ValidationError):
            Buggy(
                battery_level=80,
                status=BuggyStatus.AVAILABLE,
                current_location="invalid_location"
            )


class TestFlight:
    """Test Flight model validation."""
    
    def test_valid_flight(self):
        """Test creating a valid flight."""
        now = datetime.now(timezone.utc)
        boarding = now + timedelta(hours=1)
        departure = now + timedelta(hours=2)
        
        flight = Flight(
            id="AA123",
            departure_time=departure,
            boarding_time=boarding,
            gate="A12",
            destination="New York"
        )
        assert flight.id == "AA123"
        assert flight.status == FlightStatus.SCHEDULED
        assert flight.delay_minutes == 0
    
    def test_boarding_after_departure(self):
        """Test that boarding time must be before departure time."""
        now = datetime.now(timezone.utc)
        boarding = now + timedelta(hours=2)
        departure = now + timedelta(hours=1)
        
        with pytest.raises(ValidationError):
            Flight(
                id="AA123",
                departure_time=departure,
                boarding_time=boarding,
                gate="A12",
                destination="New York"
            )
    
    def test_empty_gate(self):
        """Test that gate cannot be empty."""
        now = datetime.now(timezone.utc)
        boarding = now + timedelta(hours=1)
        departure = now + timedelta(hours=2)
        
        with pytest.raises(ValidationError):
            Flight(
                id="AA123",
                departure_time=departure,
                boarding_time=boarding,
                gate="   ",
                destination="New York"
            )


class TestServiceLog:
    """Test ServiceLog model validation."""
    
    def test_valid_service_log(self):
        """Test creating a valid service log."""
        log = ServiceLog(
            vip_id="vip-123",
            event_type=EventType.VIP_DETECTED,
            event_data={"confidence": 0.95},
            agent_source="IdentityAgent"
        )
        assert log.vip_id == "vip-123"
        assert log.event_type == EventType.VIP_DETECTED
        assert log.agent_source == "IdentityAgent"
        assert log.id is not None
    
    def test_empty_agent_source(self):
        """Test that agent source cannot be empty."""
        with pytest.raises(ValidationError):
            ServiceLog(
                vip_id="vip-123",
                event_type=EventType.VIP_DETECTED,
                agent_source="   "
            )


class TestLoungeReservation:
    """Test LoungeReservation model validation."""
    
    def test_valid_reservation(self):
        """Test creating a valid lounge reservation."""
        reservation = LoungeReservation(
            vip_id="vip-123",
            duration_minutes=90
        )
        assert reservation.vip_id == "vip-123"
        assert reservation.status == ReservationStatus.RESERVED
        assert reservation.duration_minutes == 90
    
    def test_active_without_entry_time(self):
        """Test that active reservation must have entry time."""
        with pytest.raises(ValidationError):
            LoungeReservation(
                vip_id="vip-123",
                status=ReservationStatus.ACTIVE
            )
    
    def test_completed_without_exit_time(self):
        """Test that completed reservation must have exit time."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            LoungeReservation(
                vip_id="vip-123",
                entry_time=now,
                status=ReservationStatus.COMPLETED
            )
    
    def test_exit_before_entry(self):
        """Test that exit time cannot be before entry time."""
        now = datetime.now(timezone.utc)
        entry = now + timedelta(hours=1)
        exit_time = now
        
        with pytest.raises(ValidationError):
            LoungeReservation(
                vip_id="vip-123",
                entry_time=entry,
                exit_time=exit_time,
                status=ReservationStatus.COMPLETED
            )


class TestEvent:
    """Test Event model validation."""
    
    def test_valid_event(self):
        """Test creating a valid event."""
        event = Event(
            event_type=EventType.VIP_DETECTED,
            payload={"vip_id": "vip-123", "confidence": 0.95},
            source_agent="IdentityAgent",
            vip_id="vip-123"
        )
        assert event.event_type == EventType.VIP_DETECTED
        assert event.source_agent == "IdentityAgent"
        assert event.vip_id == "vip-123"
    
    def test_empty_source_agent(self):
        """Test that source agent cannot be empty."""
        with pytest.raises(ValidationError):
            Event(
                event_type=EventType.VIP_DETECTED,
                source_agent="   "
            )


class TestEnums:
    """Test enum values."""
    
    def test_vip_state_values(self):
        """Test VIPState enum values."""
        assert VIPState.PREPARED.value == "prepared"
        assert VIPState.ARRIVED.value == "arrived"
        assert VIPState.COMPLETED.value == "completed"
    
    def test_escort_status_values(self):
        """Test EscortStatus enum values."""
        assert EscortStatus.AVAILABLE.value == "available"
        assert EscortStatus.ASSIGNED.value == "assigned"
        assert EscortStatus.OFF_DUTY.value == "off_duty"
    
    def test_event_type_values(self):
        """Test EventType enum values."""
        assert EventType.VIP_DETECTED.value == "vip_detected"
        assert EventType.ESCORT_ASSIGNED.value == "escort_assigned"
        assert EventType.BOARDING_ALERT.value == "boarding_alert"
