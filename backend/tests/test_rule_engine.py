"""
Unit tests for Rule Engine.

Tests business rules for VIP service allocation and workflow decisions.
Validates Requirements 14.1, 14.2, 14.3, 14.4, 14.5
"""

import pytest
from backend.rule_engine import RuleEngine


class TestRuleEngine:
    """Test RuleEngine business rules."""
    
    @pytest.fixture
    def rule_engine(self):
        """Create a RuleEngine instance for testing."""
        return RuleEngine()
    
    def test_vip_gets_escort(self, rule_engine):
        """
        Test that VIP always gets escort by default.
        Validates Requirement 14.1
        """
        assert rule_engine.vip_gets_escort() is True
    
    def test_vip_gets_buggy(self, rule_engine):
        """
        Test that VIP always gets buggy by default.
        Validates Requirement 14.2
        """
        assert rule_engine.vip_gets_buggy() is True
    
    def test_lounge_pre_reserved(self, rule_engine):
        """
        Test that lounge is pre-reserved for all VIPs.
        Validates Requirement 14.3
        """
        assert rule_engine.lounge_pre_reserved() is True
    
    def test_boarding_alert_minutes(self, rule_engine):
        """
        Test that boarding alert triggers 15 minutes before boarding time.
        Validates Requirement 14.4
        """
        assert rule_engine.boarding_alert_minutes() == 15
    
    def test_should_extend_lounge_with_significant_delay(self, rule_engine):
        """
        Test that flight delay > 10 minutes extends lounge time.
        Validates Requirement 14.5
        """
        # Delays greater than 10 minutes should extend lounge
        assert rule_engine.should_extend_lounge(11) is True
        assert rule_engine.should_extend_lounge(15) is True
        assert rule_engine.should_extend_lounge(30) is True
        assert rule_engine.should_extend_lounge(60) is True
    
    def test_should_not_extend_lounge_with_minor_delay(self, rule_engine):
        """
        Test that flight delay <= 10 minutes does not extend lounge time.
        Validates Requirement 14.5
        """
        # Delays of 10 minutes or less should not extend lounge
        assert rule_engine.should_extend_lounge(10) is False
        assert rule_engine.should_extend_lounge(5) is False
        assert rule_engine.should_extend_lounge(1) is False
        assert rule_engine.should_extend_lounge(0) is False
    
    def test_should_not_extend_lounge_with_negative_delay(self, rule_engine):
        """
        Test that negative delay (early departure) does not extend lounge time.
        Validates Requirement 14.5
        """
        # Negative delays (early departures) should not extend lounge
        assert rule_engine.should_extend_lounge(-5) is False
        assert rule_engine.should_extend_lounge(-10) is False
    
    def test_should_extend_lounge_boundary_case(self, rule_engine):
        """
        Test boundary case at exactly 10 minutes delay.
        Validates Requirement 14.5
        """
        # Exactly 10 minutes should not extend (> 10, not >= 10)
        assert rule_engine.should_extend_lounge(10) is False
        # Just over 10 minutes should extend
        assert rule_engine.should_extend_lounge(11) is True


class TestRuleEngineConsistency:
    """Test that rule engine returns consistent results."""
    
    @pytest.fixture
    def rule_engine(self):
        """Create a RuleEngine instance for testing."""
        return RuleEngine()
    
    def test_vip_gets_escort_consistency(self, rule_engine):
        """Test that vip_gets_escort always returns the same value."""
        result1 = rule_engine.vip_gets_escort()
        result2 = rule_engine.vip_gets_escort()
        result3 = rule_engine.vip_gets_escort()
        assert result1 == result2 == result3 == True
    
    def test_vip_gets_buggy_consistency(self, rule_engine):
        """Test that vip_gets_buggy always returns the same value."""
        result1 = rule_engine.vip_gets_buggy()
        result2 = rule_engine.vip_gets_buggy()
        result3 = rule_engine.vip_gets_buggy()
        assert result1 == result2 == result3 == True
    
    def test_lounge_pre_reserved_consistency(self, rule_engine):
        """Test that lounge_pre_reserved always returns the same value."""
        result1 = rule_engine.lounge_pre_reserved()
        result2 = rule_engine.lounge_pre_reserved()
        result3 = rule_engine.lounge_pre_reserved()
        assert result1 == result2 == result3 == True
    
    def test_boarding_alert_minutes_consistency(self, rule_engine):
        """Test that boarding_alert_minutes always returns the same value."""
        result1 = rule_engine.boarding_alert_minutes()
        result2 = rule_engine.boarding_alert_minutes()
        result3 = rule_engine.boarding_alert_minutes()
        assert result1 == result2 == result3 == 15
    
    def test_should_extend_lounge_consistency(self, rule_engine):
        """Test that should_extend_lounge returns consistent results for same input."""
        # Test with same delay value multiple times
        delay = 20
        result1 = rule_engine.should_extend_lounge(delay)
        result2 = rule_engine.should_extend_lounge(delay)
        result3 = rule_engine.should_extend_lounge(delay)
        assert result1 == result2 == result3 == True
        
        # Test with different delay value
        delay = 5
        result1 = rule_engine.should_extend_lounge(delay)
        result2 = rule_engine.should_extend_lounge(delay)
        result3 = rule_engine.should_extend_lounge(delay)
        assert result1 == result2 == result3 == False
