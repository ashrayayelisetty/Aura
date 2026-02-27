"""
Pydantic models for AURA-VIP Orchestration System.

This module defines all data models, enums, and validation logic for the system.
Validates Requirements 15.1, 15.2, 20.1
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ============================================================================
# Enums
# ============================================================================


class VIPState(str, Enum):
    """VIP workflow state machine states."""
    PREPARED = "prepared"
    ARRIVED = "arrived"
    BUGGY_PICKUP = "buggy_pickup"
    CHECKED_IN = "checked_in"
    SECURITY_CLEARED = "security_cleared"
    LOUNGE_ENTRY = "lounge_entry"
    BUGGY_TO_GATE = "buggy_to_gate"
    BOARDED = "boarded"
    COMPLETED = "completed"


class EscortStatus(str, Enum):
    """Escort availability and assignment status."""
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    OFF_DUTY = "off_duty"


class BuggyStatus(str, Enum):
    """Buggy availability and operational status."""
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    CHARGING = "charging"
    MAINTENANCE = "maintenance"


class FlightStatus(str, Enum):
    """Flight operational status."""
    SCHEDULED = "scheduled"
    BOARDING = "boarding"
    DEPARTED = "departed"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


class ReservationStatus(str, Enum):
    """Lounge reservation status."""
    RESERVED = "reserved"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EventType(str, Enum):
    """System event types for event bus."""
    VIP_DETECTED = "vip_detected"
    STATE_CHANGED = "state_changed"
    ESCORT_ASSIGNED = "escort_assigned"
    BUGGY_DISPATCHED = "buggy_dispatched"
    LOUNGE_RESERVED = "lounge_reserved"
    LOUNGE_ENTRY = "lounge_entry"
    FLIGHT_DELAY = "flight_delay"
    BOARDING_ALERT = "boarding_alert"
    BAGGAGE_PRIORITY_TAGGED = "baggage_priority_tagged"


# ============================================================================
# Data Models
# ============================================================================


class VIPProfile(BaseModel):
    """VIP profile with face recognition data and flight information."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., min_length=1, max_length=255)
    face_embedding: List[float] = Field(..., min_length=128, max_length=128)
    flight_id: str = Field(..., min_length=1)
    current_state: VIPState = Field(default=VIPState.PREPARED)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @field_validator("face_embedding")
    @classmethod
    def validate_embedding_values(cls, v: List[float]) -> List[float]:
        """Validate that face embedding contains valid float values."""
        if not all(isinstance(x, (int, float)) for x in v):
            raise ValueError("Face embedding must contain only numeric values")
        return v
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that name is not empty or whitespace only."""
        if not v.strip():
            raise ValueError("Name cannot be empty or whitespace only")
        return v.strip()
    
    model_config = ConfigDict(use_enum_values=True)


class Escort(BaseModel):
    """Escort staff member with assignment tracking."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., min_length=1, max_length=255)
    status: EscortStatus = Field(default=EscortStatus.AVAILABLE)
    assigned_vip_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that name is not empty or whitespace only."""
        if not v.strip():
            raise ValueError("Name cannot be empty or whitespace only")
        return v.strip()
    
    @model_validator(mode="after")
    def validate_assignment(self) -> "Escort":
        """Validate that assigned escorts have a VIP ID and available escorts don't."""
        if self.status == EscortStatus.ASSIGNED and not self.assigned_vip_id:
            raise ValueError("Assigned escort must have a VIP ID")
        if self.status == EscortStatus.AVAILABLE and self.assigned_vip_id:
            raise ValueError("Available escort cannot have a VIP ID")
        return self
    
    model_config = ConfigDict(use_enum_values=True)


class Buggy(BaseModel):
    """Airport buggy with battery tracking and assignment."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    battery_level: int = Field(..., ge=0, le=100)
    status: BuggyStatus = Field(default=BuggyStatus.AVAILABLE)
    assigned_vip_id: Optional[str] = None
    current_location: str = Field(default="idle")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @field_validator("current_location")
    @classmethod
    def validate_location(cls, v: str) -> str:
        """Validate that location is one of the allowed values."""
        allowed_locations = ["idle", "en_route_pickup", "en_route_destination"]
        if v not in allowed_locations:
            raise ValueError(f"Location must be one of: {', '.join(allowed_locations)}")
        return v
    
    @model_validator(mode="after")
    def validate_assignment(self) -> "Buggy":
        """Validate buggy assignment and battery constraints."""
        if self.status == BuggyStatus.ASSIGNED and not self.assigned_vip_id:
            raise ValueError("Assigned buggy must have a VIP ID")
        if self.status == BuggyStatus.AVAILABLE and self.assigned_vip_id:
            raise ValueError("Available buggy cannot have a VIP ID")
        if self.status == BuggyStatus.ASSIGNED and self.battery_level <= 20:
            raise ValueError("Cannot assign buggy with battery level at or below 20%")
        return self
    
    model_config = ConfigDict(use_enum_values=True)


class Flight(BaseModel):
    """Flight information with scheduling and status tracking."""
    
    id: str = Field(..., min_length=1)  # Flight number
    departure_time: datetime
    boarding_time: datetime
    status: FlightStatus = Field(default=FlightStatus.SCHEDULED)
    gate: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    delay_minutes: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @model_validator(mode="after")
    def validate_times(self) -> "Flight":
        """Validate that boarding time is before departure time."""
        if self.boarding_time >= self.departure_time:
            raise ValueError("Boarding time must be before departure time")
        return self
    
    @field_validator("gate", "destination")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Validate that field is not empty or whitespace only."""
        if not v.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return v.strip()
    
    model_config = ConfigDict(use_enum_values=True)


class ServiceLog(BaseModel):
    """Service event log entry for audit trail."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    vip_id: str = Field(..., min_length=1)
    event_type: EventType
    event_data: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent_source: str = Field(..., min_length=1)
    
    @field_validator("agent_source")
    @classmethod
    def validate_agent_source(cls, v: str) -> str:
        """Validate that agent source is not empty."""
        if not v.strip():
            raise ValueError("Agent source cannot be empty")
        return v.strip()
    
    model_config = ConfigDict(use_enum_values=True)


class LoungeReservation(BaseModel):
    """Lounge reservation with timing and status tracking."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    vip_id: str = Field(..., min_length=1)
    reservation_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    duration_minutes: int = Field(default=90, gt=0)
    status: ReservationStatus = Field(default=ReservationStatus.RESERVED)
    
    @model_validator(mode="after")
    def validate_times(self) -> "LoungeReservation":
        """Validate time sequence and status consistency."""
        if self.entry_time and self.entry_time < self.reservation_time:
            raise ValueError("Entry time cannot be before reservation time")
        
        if self.exit_time:
            if not self.entry_time:
                raise ValueError("Exit time requires entry time to be set")
            if self.exit_time < self.entry_time:
                raise ValueError("Exit time cannot be before entry time")
        
        # Validate status consistency
        if self.status == ReservationStatus.ACTIVE and not self.entry_time:
            raise ValueError("Active reservation must have entry time")
        
        if self.status == ReservationStatus.COMPLETED and not self.exit_time:
            raise ValueError("Completed reservation must have exit time")
        
        return self
    
    model_config = ConfigDict(use_enum_values=True)


class Event(BaseModel):
    """System event for event bus communication."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    payload: dict = Field(default_factory=dict)
    source_agent: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    vip_id: Optional[str] = None
    
    @field_validator("source_agent")
    @classmethod
    def validate_source_agent(cls, v: str) -> str:
        """Validate that source agent is not empty."""
        if not v.strip():
            raise ValueError("Source agent cannot be empty")
        return v.strip()
    
    model_config = ConfigDict(use_enum_values=True)
