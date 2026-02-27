"""
Unit tests for Lounge Agent.

Tests lounge reservation management, capacity checking, and access control.
"""

import asyncio
import os
import pytest
import numpy as np
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agents.lounge_agent import LoungeAgent
from backend.models.schemas import Event, EventType, ReservationStatus, VIPState
from backend.orchestrator.event_bus import EventBus
from backend.database.models import LoungeReservationDB, VIPProfileDB


@pytest.fixture
def event_bus():
    """Create a mock event bus."""
    bus = MagicMock(spec=EventBus)
    bus.subscribe = MagicMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def lounge_agent(event_bus):
    """Create a lounge agent instance."""
    # Set environment variables for testing
    os.environ["LOUNGE_MAX_CAPACITY"] = "50"
    os.environ["LOUNGE_DEFAULT_DURATION_MINUTES"] = "90"
    os.environ["FACE_CONFIDENCE_THRESHOLD"] = "0.85"
    
    agent = LoungeAgent(event_bus)
    return agent


@pytest.mark.asyncio
async def test_lounge_agent_initialization(lounge_agent, event_bus):
    """Test that lounge agent initializes and subscribes to events."""
    # Verify subscriptions
    assert event_bus.subscribe.call_count == 3
    
    # Verify configuration
    assert lounge_agent.max_capacity == 50
    assert lounge_agent.default_duration == 90
    assert lounge_agent.confidence_threshold == 0.85


@pytest.mark.asyncio
async def test_create_reservation_success(lounge_agent, event_bus):
    """Test creating a lounge reservation when under capacity."""
    vip_id = "test-vip-1"
    
    with patch("backend.agents.lounge_agent.SessionLocal") as mock_session:
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.close = MagicMock()
        
        # Mock occupancy check (under capacity)
        with patch.object(lounge_agent, "_get_current_occupancy", return_value=10):
            await lounge_agent.create_reservation(vip_id)
        
        # Verify reservation was added
        assert mock_db.add.called
        assert mock_db.commit.called
        
        # Verify LOUNGE_RESERVED event was published
        assert event_bus.publish.called
        published_event = event_bus.publish.call_args[0][0]
        assert published_event.event_type == EventType.LOUNGE_RESERVED
        assert published_event.vip_id == vip_id


@pytest.mark.asyncio
async def test_create_reservation_at_capacity(lounge_agent, event_bus):
    """Test queueing reservation when at capacity."""
    vip_id = "test-vip-1"
    
    with patch("backend.agents.lounge_agent.SessionLocal") as mock_session:
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.close = MagicMock()
        
        # Mock occupancy check (at capacity)
        with patch.object(lounge_agent, "_get_current_occupancy", return_value=50):
            await lounge_agent.create_reservation(vip_id)
        
        # Verify reservation was queued
        assert vip_id in lounge_agent.reservation_queue
        
        # Verify no database add was called
        assert not mock_db.add.called
        
        # Verify no event was published
        assert not event_bus.publish.called


@pytest.mark.asyncio
async def test_grant_access(lounge_agent, event_bus):
    """Test granting lounge access to a VIP."""
    vip_id = "test-vip-1"
    
    with patch("backend.agents.lounge_agent.SessionLocal") as mock_session:
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.close = MagicMock()
        
        # Mock reservation query
        mock_reservation = MagicMock(spec=LoungeReservationDB)
        mock_reservation.id = "res-1"
        mock_reservation.vip_id = vip_id
        mock_reservation.status = ReservationStatus.RESERVED.value
        
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_reservation
        
        # Mock occupancy
        with patch.object(lounge_agent, "_get_current_occupancy", return_value=11):
            await lounge_agent.grant_access(vip_id)
        
        # Verify reservation was updated
        assert mock_reservation.status == ReservationStatus.ACTIVE.value
        assert mock_reservation.entry_time is not None
        assert mock_db.commit.called
        
        # Verify LOUNGE_ENTRY event was published
        assert event_bus.publish.called
        published_event = event_bus.publish.call_args[0][0]
        assert published_event.event_type == EventType.LOUNGE_ENTRY
        assert published_event.vip_id == vip_id


@pytest.mark.asyncio
async def test_extend_reservation(lounge_agent, event_bus):
    """Test extending a reservation due to flight delay."""
    vip_id = "test-vip-1"
    additional_minutes = 30
    
    with patch("backend.agents.lounge_agent.SessionLocal") as mock_session:
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.close = MagicMock()
        
        # Mock reservation query
        mock_reservation = MagicMock(spec=LoungeReservationDB)
        mock_reservation.id = "res-1"
        mock_reservation.vip_id = vip_id
        mock_reservation.duration_minutes = 90
        
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_reservation
        
        await lounge_agent.extend_reservation(vip_id, additional_minutes)
        
        # Verify duration was extended
        assert mock_reservation.duration_minutes == 120
        assert mock_db.commit.called


@pytest.mark.asyncio
async def test_release_reservation(lounge_agent, event_bus):
    """Test releasing a reservation when VIP departs."""
    vip_id = "test-vip-1"
    
    with patch("backend.agents.lounge_agent.SessionLocal") as mock_session:
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.close = MagicMock()
        
        # Mock reservation query
        mock_reservation = MagicMock(spec=LoungeReservationDB)
        mock_reservation.id = "res-1"
        mock_reservation.vip_id = vip_id
        mock_reservation.status = ReservationStatus.ACTIVE.value
        
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_reservation
        
        await lounge_agent.release_reservation(vip_id)
        
        # Verify reservation was completed
        assert mock_reservation.status == ReservationStatus.COMPLETED.value
        assert mock_reservation.exit_time is not None
        assert mock_db.commit.called


@pytest.mark.asyncio
async def test_release_reservation_processes_queue(lounge_agent, event_bus):
    """Test that releasing a reservation processes queued reservations."""
    vip_id = "test-vip-1"
    queued_vip_id = "test-vip-2"
    
    # Add VIP to queue
    lounge_agent.reservation_queue.append(queued_vip_id)
    
    with patch("backend.agents.lounge_agent.SessionLocal") as mock_session:
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.close = MagicMock()
        
        # Mock reservation query
        mock_reservation = MagicMock(spec=LoungeReservationDB)
        mock_reservation.id = "res-1"
        mock_reservation.vip_id = vip_id
        mock_reservation.status = ReservationStatus.ACTIVE.value
        
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_reservation
        
        # Mock create_reservation to avoid actual database operations
        with patch.object(lounge_agent, "create_reservation", new_callable=AsyncMock) as mock_create:
            await lounge_agent.release_reservation(vip_id)
            
            # Verify queued VIP was processed
            mock_create.assert_called_once_with(queued_vip_id)


@pytest.mark.asyncio
async def test_verify_lounge_entry_success(lounge_agent, event_bus):
    """Test successful face verification at lounge entry."""
    vip_id = "test-vip-1"
    
    # Create test face embedding
    test_embedding = np.random.rand(128).astype(np.float64)
    
    with patch("backend.agents.lounge_agent.SessionLocal") as mock_session:
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.close = MagicMock()
        
        # Mock reservation query
        mock_reservation = MagicMock(spec=LoungeReservationDB)
        mock_reservation.vip_id = vip_id
        
        # Mock VIP profile query
        mock_vip = MagicMock(spec=VIPProfileDB)
        mock_vip.id = vip_id
        mock_vip.face_embedding = test_embedding.tobytes()
        
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_reservation]
        
        # Second query for VIP profiles
        def query_side_effect(model):
            if model == LoungeReservationDB:
                return mock_query
            elif model == VIPProfileDB:
                vip_query = MagicMock()
                vip_query.filter.return_value = vip_query
                vip_query.all.return_value = [mock_vip]
                return vip_query
        
        mock_db.query.side_effect = query_side_effect
        
        # Verify with same embedding (should have high confidence)
        result = await lounge_agent.verify_lounge_entry(test_embedding)
        
        # Should match the VIP
        assert result == vip_id


@pytest.mark.asyncio
async def test_verify_lounge_entry_low_confidence(lounge_agent, event_bus):
    """Test face verification failure due to low confidence."""
    vip_id = "test-vip-1"
    
    # Create test face embeddings (different)
    test_embedding = np.random.rand(128).astype(np.float64)
    stored_embedding = np.random.rand(128).astype(np.float64)
    
    with patch("backend.agents.lounge_agent.SessionLocal") as mock_session:
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.close = MagicMock()
        
        # Mock reservation query
        mock_reservation = MagicMock(spec=LoungeReservationDB)
        mock_reservation.vip_id = vip_id
        
        # Mock VIP profile query
        mock_vip = MagicMock(spec=VIPProfileDB)
        mock_vip.id = vip_id
        mock_vip.face_embedding = stored_embedding.tobytes()
        
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [mock_reservation]
        
        # Second query for VIP profiles
        def query_side_effect(model):
            if model == LoungeReservationDB:
                return mock_query
            elif model == VIPProfileDB:
                vip_query = MagicMock()
                vip_query.filter.return_value = vip_query
                vip_query.all.return_value = [mock_vip]
                return vip_query
        
        mock_db.query.side_effect = query_side_effect
        
        # Verify with different embedding (should have low confidence)
        result = await lounge_agent.verify_lounge_entry(test_embedding)
        
        # Should not match (random embeddings unlikely to have >0.85 similarity)
        assert result is None


@pytest.mark.asyncio
async def test_handle_vip_detected(lounge_agent, event_bus):
    """Test handling VIP_DETECTED event."""
    vip_id = "test-vip-1"
    
    event = Event(
        event_type=EventType.VIP_DETECTED,
        payload={"vip_id": vip_id},
        source_agent="identity_agent",
        vip_id=vip_id
    )
    
    with patch.object(lounge_agent, "create_reservation", new_callable=AsyncMock) as mock_create:
        await lounge_agent.handle_vip_detected(event)
        
        # Verify create_reservation was called
        mock_create.assert_called_once_with(vip_id)


@pytest.mark.asyncio
async def test_handle_flight_delay(lounge_agent, event_bus):
    """Test handling FLIGHT_DELAY event."""
    vip_id = "test-vip-1"
    delay_minutes = 30
    
    event = Event(
        event_type=EventType.FLIGHT_DELAY,
        payload={"vip_id": vip_id, "delay_minutes": delay_minutes},
        source_agent="flight_intelligence_agent",
        vip_id=vip_id
    )
    
    with patch.object(lounge_agent, "extend_reservation", new_callable=AsyncMock) as mock_extend:
        await lounge_agent.handle_flight_delay(event)
        
        # Verify extend_reservation was called
        mock_extend.assert_called_once_with(vip_id, delay_minutes)


@pytest.mark.asyncio
async def test_handle_state_changed_buggy_to_gate(lounge_agent, event_bus):
    """Test handling STATE_CHANGED event when VIP departs lounge."""
    vip_id = "test-vip-1"
    
    event = Event(
        event_type=EventType.STATE_CHANGED,
        payload={"vip_id": vip_id, "new_state": VIPState.BUGGY_TO_GATE.value},
        source_agent="master_orchestrator",
        vip_id=vip_id
    )
    
    with patch.object(lounge_agent, "release_reservation", new_callable=AsyncMock) as mock_release:
        await lounge_agent.handle_state_changed(event)
        
        # Verify release_reservation was called
        mock_release.assert_called_once_with(vip_id)


@pytest.mark.asyncio
async def test_get_current_occupancy(lounge_agent, event_bus):
    """Test getting current lounge occupancy."""
    with patch("backend.agents.lounge_agent.SessionLocal") as mock_session:
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_db.close = MagicMock()
        
        # Mock query count
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 15
        
        occupancy = await lounge_agent._get_current_occupancy()
        
        # Verify occupancy count
        assert occupancy == 15
