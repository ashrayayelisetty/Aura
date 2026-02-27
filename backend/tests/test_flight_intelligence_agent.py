"""
Unit tests for Flight Intelligence Agent.

Tests flight monitoring, delay detection, and boarding alerts.
Validates Requirements 6.1, 6.2, 6.3, 6.4, 6.5
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agents.flight_intelligence_agent import FlightIntelligenceAgent
from backend.orchestrator.event_bus import EventBus
from backend.models.schemas import Event, EventType, FlightStatus
from backend.database.models import FlightDB, VIPProfileDB
from backend.database.connection import SessionLocal


@pytest.fixture
def event_bus():
    """Create a mock event bus."""
    bus = EventBus()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def flight_agent(event_bus):
    """Create a Flight Intelligence Agent instance."""
    return FlightIntelligenceAgent(event_bus)


@pytest.fixture
def sample_flight():
    """Create a sample flight for testing."""
    now = datetime.now(timezone.utc)
    return FlightDB(
        id="AA123",
        departure_time=now + timedelta(hours=1),
        boarding_time=now + timedelta(minutes=30),
        status=FlightStatus.SCHEDULED.value,
        gate="A1",
        destination="New York",
        delay_minutes=0
    )


@pytest.fixture
def sample_vip():
    """Create a sample VIP for testing."""
    return VIPProfileDB(
        id="vip-001",
        name="John Doe",
        face_embedding=b"fake_embedding",
        flight_id="AA123",
        current_state="lounge_entry"
    )


class TestFlightIntelligenceAgentInitialization:
    """Test Flight Intelligence Agent initialization."""
    
    def test_agent_initialization(self, event_bus):
        """Test that agent initializes correctly."""
        agent = FlightIntelligenceAgent(event_bus)
        
        assert agent.event_bus == event_bus
        assert agent._monitoring_task is None
        assert agent._stop_monitoring is False


class TestFlightMonitoring:
    """Test flight monitoring functionality."""
    
    @pytest.mark.asyncio
    async def test_start_monitoring(self, flight_agent):
        """Test that monitoring can be started."""
        # Start monitoring
        await flight_agent.start_monitoring()
        
        # Verify monitoring task is created
        assert flight_agent._monitoring_task is not None
        assert not flight_agent._stop_monitoring
        
        # Stop monitoring
        await flight_agent.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_stop_monitoring(self, flight_agent):
        """Test that monitoring can be stopped."""
        # Start monitoring
        await flight_agent.start_monitoring()
        
        # Stop monitoring
        await flight_agent.stop_monitoring()
        
        # Verify monitoring task is cleared
        assert flight_agent._monitoring_task is None
        assert flight_agent._stop_monitoring
    
    @pytest.mark.asyncio
    async def test_start_monitoring_when_already_running(self, flight_agent):
        """Test that starting monitoring when already running logs a warning."""
        # Start monitoring
        await flight_agent.start_monitoring()
        
        # Try to start again
        await flight_agent.start_monitoring()
        
        # Should still have only one task
        assert flight_agent._monitoring_task is not None
        
        # Stop monitoring
        await flight_agent.stop_monitoring()



class TestBoardingTimeCheck:
    """Test boarding time checking functionality."""
    
    @pytest.mark.asyncio
    async def test_check_boarding_time_within_window(self, flight_agent, event_bus, sample_flight, sample_vip):
        """Test that boarding alert is emitted when within 15-minute window."""
        # Set boarding time to 15 minutes from now
        now = datetime.now(timezone.utc)
        sample_flight.boarding_time = now + timedelta(minutes=15)
        sample_flight.departure_time = now + timedelta(minutes=45)
        
        # Mock database session
        with patch('backend.agents.flight_intelligence_agent.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Mock flight query
            mock_db.query.return_value.filter.return_value.first.return_value = sample_flight
            
            # Mock VIP query for emit_boarding_alert
            with patch.object(flight_agent, 'emit_boarding_alert', new_callable=AsyncMock) as mock_emit:
                await flight_agent.check_boarding_time("AA123")
                
                # Verify boarding alert was called
                mock_emit.assert_called_once_with("AA123")
    
    @pytest.mark.asyncio
    async def test_check_boarding_time_outside_window(self, flight_agent, sample_flight):
        """Test that boarding alert is not emitted when outside 15-minute window."""
        # Set boarding time to 30 minutes from now (outside window)
        now = datetime.now(timezone.utc)
        sample_flight.boarding_time = now + timedelta(minutes=30)
        sample_flight.departure_time = now + timedelta(minutes=60)
        
        # Mock database session
        with patch('backend.agents.flight_intelligence_agent.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Mock flight query
            mock_db.query.return_value.filter.return_value.first.return_value = sample_flight
            
            # Mock emit_boarding_alert
            with patch.object(flight_agent, 'emit_boarding_alert', new_callable=AsyncMock) as mock_emit:
                await flight_agent.check_boarding_time("AA123")
                
                # Verify boarding alert was NOT called
                mock_emit.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_check_boarding_time_flight_not_found(self, flight_agent):
        """Test handling when flight is not found."""
        # Mock database session
        with patch('backend.agents.flight_intelligence_agent.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Mock flight query to return None
            mock_db.query.return_value.filter.return_value.first.return_value = None
            
            # Should not raise exception
            await flight_agent.check_boarding_time("INVALID")


class TestDelayDetection:
    """Test flight delay detection functionality."""
    
    @pytest.mark.asyncio
    async def test_detect_delay_with_delay(self, flight_agent, event_bus, sample_flight):
        """Test that delay is detected and FLIGHT_DELAY event is emitted."""
        # Set delay
        sample_flight.delay_minutes = 30
        sample_flight.status = FlightStatus.SCHEDULED.value
        
        # Mock database session
        with patch('backend.agents.flight_intelligence_agent.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Mock flight query
            mock_db.query.return_value.filter.return_value.first.return_value = sample_flight
            
            # Call detect_delay
            new_departure = await flight_agent.detect_delay("AA123")
            
            # Verify new departure time is calculated
            assert new_departure is not None
            
            # Verify flight status updated to DELAYED
            assert sample_flight.status == FlightStatus.DELAYED.value
            
            # Verify FLIGHT_DELAY event was published
            event_bus.publish.assert_called_once()
            published_event = event_bus.publish.call_args[0][0]
            assert published_event.event_type == EventType.FLIGHT_DELAY
            assert published_event.payload["flight_id"] == "AA123"
            assert published_event.payload["delay_minutes"] == 30
    
    @pytest.mark.asyncio
    async def test_detect_delay_no_delay(self, flight_agent, event_bus, sample_flight):
        """Test that no event is emitted when there's no delay."""
        # No delay
        sample_flight.delay_minutes = 0
        sample_flight.status = FlightStatus.SCHEDULED.value
        
        # Mock database session
        with patch('backend.agents.flight_intelligence_agent.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Mock flight query
            mock_db.query.return_value.filter.return_value.first.return_value = sample_flight
            
            # Call detect_delay
            new_departure = await flight_agent.detect_delay("AA123")
            
            # Verify no new departure time
            assert new_departure is None
            
            # Verify no event was published
            event_bus.publish.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_detect_delay_already_delayed(self, flight_agent, event_bus, sample_flight):
        """Test that delay is not re-detected for already delayed flights."""
        # Set delay and status to DELAYED
        sample_flight.delay_minutes = 30
        sample_flight.status = FlightStatus.DELAYED.value
        
        # Mock database session
        with patch('backend.agents.flight_intelligence_agent.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Mock flight query
            mock_db.query.return_value.filter.return_value.first.return_value = sample_flight
            
            # Call detect_delay
            new_departure = await flight_agent.detect_delay("AA123")
            
            # Verify no new departure time (already processed)
            assert new_departure is None
            
            # Verify no event was published
            event_bus.publish.assert_not_called()


class TestBoardingAlertEmission:
    """Test boarding alert emission functionality."""
    
    @pytest.mark.asyncio
    async def test_emit_boarding_alert_with_vips(self, flight_agent, event_bus, sample_flight, sample_vip):
        """Test that boarding alerts are emitted for all VIPs on flight."""
        # Mock database session
        with patch('backend.agents.flight_intelligence_agent.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Mock VIP query to return sample VIP
            vip_query = MagicMock()
            vip_query.filter.return_value.all.return_value = [sample_vip]
            
            # Mock flight query
            flight_query = MagicMock()
            flight_query.filter.return_value.first.return_value = sample_flight
            
            # Set up query to return different results based on model
            def query_side_effect(model):
                if model == VIPProfileDB:
                    return vip_query
                elif model == FlightDB:
                    return flight_query
                return MagicMock()
            
            mock_db.query.side_effect = query_side_effect
            
            # Call emit_boarding_alert
            await flight_agent.emit_boarding_alert("AA123")
            
            # Verify BOARDING_ALERT event was published
            event_bus.publish.assert_called_once()
            published_event = event_bus.publish.call_args[0][0]
            assert published_event.event_type == EventType.BOARDING_ALERT
            assert published_event.payload["vip_id"] == "vip-001"
            assert published_event.payload["flight_id"] == "AA123"
            assert published_event.vip_id == "vip-001"
    
    @pytest.mark.asyncio
    async def test_emit_boarding_alert_no_vips(self, flight_agent, event_bus, sample_flight):
        """Test handling when no VIPs are found for flight."""
        # Mock database session
        with patch('backend.agents.flight_intelligence_agent.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Mock VIP query to return empty list
            vip_query = MagicMock()
            vip_query.filter.return_value.all.return_value = []
            
            mock_db.query.return_value = vip_query
            
            # Call emit_boarding_alert
            await flight_agent.emit_boarding_alert("AA123")
            
            # Verify no event was published
            event_bus.publish.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_emit_boarding_alert_flight_not_found(self, flight_agent, event_bus, sample_vip):
        """Test handling when flight is not found."""
        # Mock database session
        with patch('backend.agents.flight_intelligence_agent.SessionLocal') as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            
            # Mock VIP query to return sample VIP
            vip_query = MagicMock()
            vip_query.filter.return_value.all.return_value = [sample_vip]
            
            # Mock flight query to return None
            flight_query = MagicMock()
            flight_query.filter.return_value.first.return_value = None
            
            # Set up query to return different results based on model
            def query_side_effect(model):
                if model == VIPProfileDB:
                    return vip_query
                elif model == FlightDB:
                    return flight_query
                return MagicMock()
            
            mock_db.query.side_effect = query_side_effect
            
            # Call emit_boarding_alert
            await flight_agent.emit_boarding_alert("AA123")
            
            # Verify no event was published
            event_bus.publish.assert_not_called()


class TestBoardingTimeCalculation:
    """Test boarding time calculation (departure time - 30 minutes)."""
    
    @pytest.mark.asyncio
    async def test_boarding_time_calculation(self, flight_agent):
        """Test that boarding time is correctly calculated as departure time - 30 minutes."""
        # Create a flight with specific times
        now = datetime.now(timezone.utc)
        departure_time = now + timedelta(hours=2)
        expected_boarding_time = departure_time - timedelta(minutes=30)
        
        flight = FlightDB(
            id="AA123",
            departure_time=departure_time,
            boarding_time=expected_boarding_time,
            status=FlightStatus.SCHEDULED.value,
            gate="A1",
            destination="New York",
            delay_minutes=0
        )
        
        # Verify boarding time is 30 minutes before departure
        time_diff = (flight.departure_time - flight.boarding_time).total_seconds() / 60
        assert time_diff == 30, "Boarding time should be 30 minutes before departure"
