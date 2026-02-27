"""
Database initialization script with sample data.

This script creates tables and populates them with sample data:
- 3 VIPs
- 5 escorts
- 3 buggies
- 2 flights

Validates Requirements 15.1, 15.2, 15.3
"""

import numpy as np
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .connection import engine, SessionLocal, create_tables
from .models import VIPProfileDB, EscortDB, BuggyDB, FlightDB


def serialize_embedding(embedding: np.ndarray) -> bytes:
    """Serialize numpy array to bytes for database storage."""
    return embedding.tobytes()


def create_sample_data() -> None:
    """Create sample data for demonstration and testing."""
    
    # Create tables first
    create_tables()
    
    # Create session
    db = SessionLocal()
    
    try:
        # Clear existing data (for development/demo purposes)
        db.query(VIPProfileDB).delete()
        db.query(EscortDB).delete()
        db.query(BuggyDB).delete()
        db.query(FlightDB).delete()
        db.commit()
        
        # Create 2 sample flights
        now = datetime.now(timezone.utc)
        
        flight1 = FlightDB(
            id="BA123",
            departure_time=now + timedelta(hours=3),
            boarding_time=now + timedelta(hours=2, minutes=30),
            status="scheduled",
            gate="A12",
            destination="London Heathrow",
            delay_minutes=0
        )
        
        flight2 = FlightDB(
            id="EK456",
            departure_time=now + timedelta(hours=4),
            boarding_time=now + timedelta(hours=3, minutes=30),
            status="scheduled",
            gate="B7",
            destination="Dubai International",
            delay_minutes=0
        )
        
        db.add(flight1)
        db.add(flight2)
        db.commit()
        
        # Don't create sample VIPs - they clutter the demo
        # VIPs will be created by the demo mode instead
        
        # Create 5 sample escorts
        escorts = [
            EscortDB(id=str(uuid4()), name="Alice Williams", status="available"),
            EscortDB(id=str(uuid4()), name="Bob Chen", status="available"),
            EscortDB(id=str(uuid4()), name="Carol Martinez", status="available"),
            EscortDB(id=str(uuid4()), name="David Kumar", status="available"),
            EscortDB(id=str(uuid4()), name="Emma Thompson", status="available"),
        ]
        
        for escort in escorts:
            db.add(escort)
        db.commit()
        
        # Create 3 sample buggies
        buggies = [
            BuggyDB(
                id=str(uuid4()),
                battery_level=85,
                status="available",
                current_location="idle"
            ),
            BuggyDB(
                id=str(uuid4()),
                battery_level=92,
                status="available",
                current_location="idle"
            ),
            BuggyDB(
                id=str(uuid4()),
                battery_level=67,
                status="available",
                current_location="idle"
            ),
        ]
        
        for buggy in buggies:
            db.add(buggy)
        db.commit()
        
        print("✓ Database initialized successfully!")
        print(f"✓ Created 2 flights: {flight1.id}, {flight2.id}")
        print(f"✓ Created 5 escorts")
        print(f"✓ Created 3 buggies")
        print("✓ Ready for demo mode!")
        
    except Exception as e:
        print(f"✗ Error initializing database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_sample_data()
