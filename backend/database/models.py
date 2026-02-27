"""
SQLAlchemy database models for AURA-VIP Orchestration System.

This module defines the database schema with tables, relationships, and indexes.
Validates Requirements 15.1, 15.2, 15.3
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, ForeignKey, Index, JSON, LargeBinary
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class VIPProfileDB(Base):
    """VIP profile table with face recognition data."""
    __tablename__ = "vip_profiles"
    
    id = Column(String, primary_key=True)
    name = Column(String(255), nullable=False)
    face_embedding = Column(LargeBinary, nullable=False)  # Serialized numpy array
    flight_id = Column(String, ForeignKey("flights.id"), nullable=False)
    current_state = Column(String(50), nullable=False, default="prepared")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    flight = relationship("FlightDB", back_populates="vips")
    service_logs = relationship("ServiceLogDB", back_populates="vip", cascade="all, delete-orphan")
    lounge_reservations = relationship("LoungeReservationDB", back_populates="vip", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_vip_flight_id", "flight_id"),
        Index("idx_vip_current_state", "current_state"),
    )


class EscortDB(Base):
    """Escort staff member table."""
    __tablename__ = "escorts"
    
    id = Column(String, primary_key=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="available")
    assigned_vip_id = Column(String, ForeignKey("vip_profiles.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_escort_status", "status"),
    )


class BuggyDB(Base):
    """Airport buggy table with battery tracking."""
    __tablename__ = "buggies"
    
    id = Column(String, primary_key=True)
    battery_level = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False, default="available")
    assigned_vip_id = Column(String, ForeignKey("vip_profiles.id"), nullable=True)
    current_location = Column(String(50), nullable=False, default="idle")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_buggy_status", "status"),
    )


class FlightDB(Base):
    """Flight information table."""
    __tablename__ = "flights"
    
    id = Column(String, primary_key=True)  # Flight number
    departure_time = Column(DateTime, nullable=False)
    boarding_time = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False, default="scheduled")
    gate = Column(String(10), nullable=False)
    destination = Column(String(255), nullable=False)
    delay_minutes = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    vips = relationship("VIPProfileDB", back_populates="flight")


class ServiceLogDB(Base):
    """Service event log table for audit trail."""
    __tablename__ = "service_logs"
    
    id = Column(String, primary_key=True)
    vip_id = Column(String, ForeignKey("vip_profiles.id"), nullable=False)
    event_type = Column(String(50), nullable=False)
    event_data = Column(JSON, nullable=False, default=dict)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    agent_source = Column(String(100), nullable=False)
    
    # Relationships
    vip = relationship("VIPProfileDB", back_populates="service_logs")
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_service_log_vip_id", "vip_id"),
        Index("idx_service_log_timestamp", "timestamp"),
    )


class LoungeReservationDB(Base):
    """Lounge reservation table."""
    __tablename__ = "lounge_reservations"
    
    id = Column(String, primary_key=True)
    vip_id = Column(String, ForeignKey("vip_profiles.id"), nullable=False)
    reservation_time = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    entry_time = Column(DateTime, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=False, default=90)
    status = Column(String(50), nullable=False, default="reserved")
    
    # Relationships
    vip = relationship("VIPProfileDB", back_populates="lounge_reservations")
