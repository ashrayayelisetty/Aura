"""
Agents Module

Contains all specialized agents for VIP service orchestration.
"""

# Lazy imports to avoid loading heavy dependencies during testing
def __getattr__(name):
    if name == "IdentityAgent":
        from backend.agents.identity_agent import IdentityAgent
        return IdentityAgent
    elif name == "EscortAgent":
        from backend.agents.escort_agent import EscortAgent
        return EscortAgent
    elif name == "TransportAgent":
        from backend.agents.transport_agent import TransportAgent
        return TransportAgent
    elif name == "LoungeAgent":
        from backend.agents.lounge_agent import LoungeAgent
        return LoungeAgent
    elif name == "FlightIntelligenceAgent":
        from backend.agents.flight_intelligence_agent import FlightIntelligenceAgent
        return FlightIntelligenceAgent
    elif name == "BaggageAgent":
        from backend.agents.baggage_agent import BaggageAgent
        return BaggageAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["IdentityAgent", "EscortAgent", "TransportAgent", "LoungeAgent", "FlightIntelligenceAgent", "BaggageAgent"]
