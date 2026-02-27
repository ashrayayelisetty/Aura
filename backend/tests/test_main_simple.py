"""
Simple integration test for main.py endpoints.
Tests that the FastAPI application can be imported and basic endpoints work.
"""

import pytest
from datetime import datetime, timezone, timedelta
import numpy as np

# Test that main.py can be imported without errors
def test_import_main():
    """Test that main.py can be imported successfully."""
    try:
        from backend import main
        assert main.app is not None
        assert hasattr(main, 'list_vips')
        assert hasattr(main, 'get_vip_details')
        assert hasattr(main, 'list_escorts')
        assert hasattr(main, 'list_buggies')
        assert hasattr(main, 'get_lounge_status')
        assert hasattr(main, 'list_flights')
        assert hasattr(main, 'websocket_endpoint')
    except Exception as e:
        pytest.fail(f"Failed to import main.py: {e}")


def test_app_configuration():
    """Test that the FastAPI app is configured correctly."""
    from backend.main import app
    
    assert app.title == "AURA-VIP Orchestration System"
    assert app.version == "1.0.0"
    assert app.description == "AI-powered airport VIP concierge system"


def test_routes_registered():
    """Test that all required routes are registered."""
    from backend.main import app
    
    routes = [route.path for route in app.routes]
    
    # Check that all required endpoints are registered
    assert "/" in routes
    assert "/api/health" in routes
    assert "/api/vips" in routes
    assert "/api/vips/{vip_id}" in routes
    assert "/api/escorts" in routes
    assert "/api/buggies" in routes
    assert "/api/lounge" in routes
    assert "/api/flights" in routes
    assert "/ws" in routes


def test_database_models_import():
    """Test that database models can be imported."""
    from backend.database.models import (
        VIPProfileDB, EscortDB, BuggyDB, FlightDB,
        LoungeReservationDB, ServiceLogDB
    )
    
    assert VIPProfileDB is not None
    assert EscortDB is not None
    assert BuggyDB is not None
    assert FlightDB is not None
    assert LoungeReservationDB is not None
    assert ServiceLogDB is not None


def test_agents_import():
    """Test that all agents can be imported."""
    from backend.agents.identity_agent import IdentityAgent
    from backend.agents.escort_agent import EscortAgent
    from backend.agents.transport_agent import TransportAgent
    from backend.agents.lounge_agent import LoungeAgent
    from backend.agents.flight_intelligence_agent import FlightIntelligenceAgent
    from backend.agents.baggage_agent import BaggageAgent
    
    assert IdentityAgent is not None
    assert EscortAgent is not None
    assert TransportAgent is not None
    assert LoungeAgent is not None
    assert FlightIntelligenceAgent is not None
    assert BaggageAgent is not None


def test_orchestrator_import():
    """Test that orchestrator components can be imported."""
    from backend.orchestrator.event_bus import EventBus
    from backend.orchestrator.master_orchestrator import MasterOrchestrator
    
    assert EventBus is not None
    assert MasterOrchestrator is not None


def test_websocket_manager_import():
    """Test that WebSocket manager can be imported."""
    from backend.websocket.manager import WebSocketManager
    
    assert WebSocketManager is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
