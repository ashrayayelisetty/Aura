"""
Rule Engine for AURA-VIP System

Centralizes business rules for VIP service allocation and workflow decisions.
"""


class RuleEngine:
    """
    Rule-based decision engine for VIP service policies.
    
    This class enforces business rules for:
    - Resource assignment (escorts, buggies, lounge)
    - Timing rules (boarding alerts)
    - Workflow adjustments (flight delays)
    """
    
    def vip_gets_escort(self) -> bool:
        """
        VIP always gets escort by default.
        
        Returns:
            bool: True (VIPs always receive escort assignment)
        """
        return True
    
    def vip_gets_buggy(self) -> bool:
        """
        VIP always gets buggy by default.
        
        Returns:
            bool: True (VIPs always receive buggy assignment)
        """
        return True
    
    def lounge_pre_reserved(self) -> bool:
        """
        Lounge is pre-reserved for all VIPs.
        
        Returns:
            bool: True (Lounge reservations are created automatically)
        """
        return True
    
    def boarding_alert_minutes(self) -> int:
        """
        Boarding alert triggers N minutes before boarding time.
        
        Returns:
            int: 15 (minutes before boarding to trigger alert)
        """
        return 15
    
    def should_extend_lounge(self, delay_minutes: int) -> bool:
        """
        Flight delay extends lounge time and reschedules buggy dispatch.
        
        Args:
            delay_minutes: Number of minutes the flight is delayed
            
        Returns:
            bool: True if delay is significant enough to extend lounge time
        """
        return delay_minutes > 10
