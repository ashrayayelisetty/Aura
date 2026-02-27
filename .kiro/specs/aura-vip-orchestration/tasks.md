# Implementation Plan: AURA-VIP Orchestration System

## Overview

This implementation plan breaks down the AURA-VIP system into incremental, testable steps. The system is an event-driven, multi-agent airport VIP orchestration platform built with Python (FastAPI backend), React (frontend), PostgreSQL/SQLite (database), and WebSocket for real-time communication.

The implementation follows a bottom-up approach: core infrastructure first (database, event bus, models), then agents, then orchestrator, then frontend, and finally integration and testing.

## Tasks

- [x] 1. Set up project structure and core infrastructure
  - Create backend directory structure: `main.py`, `orchestrator/`, `agents/`, `models/`, `database/`, `rule_engine/`, `websocket/`
  - Create frontend directory structure: `src/pages/`, `src/components/`, `src/services/`, `src/socket/`
  - Set up Python virtual environment and install dependencies: FastAPI, SQLAlchemy, Pydantic, OpenCV, DeepFace, WebSockets, pytest, hypothesis
  - Set up React project with TypeScript, install dependencies: React Router, WebSocket client, TailwindCSS
  - Create `.env` file template for configuration (database URL, confidence threshold, lounge capacity)
  - _Requirements: 20.4, 20.5_

- [ ] 2. Implement database models and schema
  - [x] 2.1 Create Pydantic models for all data types
    - Implement `VIPProfile`, `Escort`, `Buggy`, `Flight`, `ServiceLog`, `LoungeReservation`, `Event` models
    - Implement enums: `VIPState`, `EscortStatus`, `BuggyStatus`, `FlightStatus`, `ReservationStatus`, `EventType`
    - Add validation logic for each model
    - _Requirements: 15.1, 15.2, 20.1_

  - [ ]* 2.2 Write property test for data model validation
    - **Property 38 (partial): Database Persistence Completeness**
    - Test that all required fields are present and validated correctly
    - **Validates: Requirements 15.1, 15.2**

  - [x] 2.3 Create SQLAlchemy database schema
    - Define tables: `vip_profiles`, `escorts`, `buggies`, `flights`, `service_logs`, `lounge_reservations`
    - Add indexes for performance: vip_profiles (flight_id, current_state), escorts (status), buggies (status), service_logs (vip_id, timestamp)
    - Create database initialization script with sample data (3 VIPs, 5 escorts, 3 buggies, 2 flights)
    - _Requirements: 15.1, 15.2, 15.3_

  - [ ]* 2.4 Write unit tests for database operations
    - Test CRUD operations for each table
    - Test query performance with indexes
    - _Requirements: 15.1, 15.2, 15.3_

- [ ] 3. Implement Event Bus
  - [x] 3.1 Create Event Bus core functionality
    - Implement event subscription registry (dict mapping event types to handler lists)
    - Implement `subscribe()` method for agent registration
    - Implement `publish()` method for event delivery to all subscribers
    - Implement `publish_with_retry()` with exponential backoff (max 3 retries)
    - Add event logging to database (service_logs table)
    - _Requirements: 13.1, 13.2, 13.4, 13.5_

  - [ ]* 3.2 Write property test for Event Bus broadcast completeness
    - **Property 3: Event Bus Broadcast Completeness**
    - Test that all subscribed agents receive events exactly once
    - **Validates: Requirements 1.4, 13.2**

  - [ ]* 3.3 Write property test for event logging
    - **Property 35: Event Logging Completeness**
    - Test that all events create log entries with required fields
    - **Validates: Requirements 13.4**

  - [ ]* 3.4 Write property test for event delivery retry
    - **Property 36: Event Delivery Retry Logic**
    - Test retry logic with simulated failures
    - **Validates: Requirements 13.5**

  - [ ]* 3.5 Write property test for event type support
    - **Property 34: Event Type Support**
    - Test that all defined event types are accepted and delivered
    - **Validates: Requirements 13.3**

- [ ] 4. Implement Rule Engine
  - [x] 4.1 Create Rule Engine with business rules
    - Implement `vip_gets_escort()` → returns True
    - Implement `vip_gets_buggy()` → returns True
    - Implement `lounge_pre_reserved()` → returns True
    - Implement `boarding_alert_minutes()` → returns 15
    - Implement `should_extend_lounge(delay_minutes)` → returns delay_minutes > 10
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_

  - [ ]* 4.2 Write property test for default resource assignment rules
    - **Property 37: Default Resource Assignment Rules**
    - Test that VIPs automatically get escort, buggy, and lounge reservation
    - **Validates: Requirements 14.1, 14.2, 14.3**

- [x] 5. Checkpoint - Ensure core infrastructure tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement Identity Agent
  - [x] 6.1 Create Identity Agent with face recognition
    - Implement `extract_embedding()` using DeepFace with VGG-Face backend
    - Implement `match_vip()` with cosine similarity matching against stored VIP profiles
    - Implement confidence threshold check (default 0.85 from config)
    - Implement `process_camera_feed()` loop (2 FPS processing rate)
    - Emit `VIP_DETECTED` event when confidence exceeds threshold
    - Log failed recognition attempts without triggering services
    - Subscribe to Event Bus during initialization
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 18.2, 18.4_

  - [ ]* 6.2 Write property test for face recognition workflow
    - **Property 1: Face Recognition Workflow Completeness**
    - Test that face images trigger embedding extraction, matching, and event emission
    - **Validates: Requirements 1.1, 1.2, 1.3**

  - [ ]* 6.3 Write property test for face recognition rejection
    - **Property 2: Face Recognition Rejection**
    - Test that low-confidence matches are logged without triggering services
    - **Validates: Requirements 1.5**

- [ ] 7. Implement Escort Agent
  - [x] 7.1 Create Escort Agent with assignment logic
    - Implement `find_available_escort()` to query escorts with status=available
    - Implement `assign_escort()` to create assignment and update escort status
    - Implement request queueing when no escorts available (FIFO queue)
    - Implement `release_escort()` to mark escort as available
    - Subscribe to `VIP_DETECTED` and `STATE_CHANGED` events
    - Emit `ESCORT_ASSIGNED` event after successful assignment
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 7.2 Write property test for escort assignment workflow
    - **Property 8: Escort Assignment Workflow**
    - Test that VIP detection triggers escort assignment and event emission
    - **Validates: Requirements 3.1, 3.2, 3.4**

  - [ ]* 7.3 Write property test for escort queue management
    - **Property 9: Escort Queue Management**
    - Test FIFO queue processing when no escorts available
    - **Validates: Requirements 3.3**

- [ ] 8. Implement Transport Agent
  - [x] 8.1 Create Transport Agent with buggy management
    - Implement `find_available_buggy()` to query buggies with battery > 20%
    - Implement `dispatch_buggy()` to assign buggy and update status
    - Implement `simulate_trip()` with battery depletion (5% per trip)
    - Implement trip duration simulation: arrival→lounge (5 min), lounge→gate (7 min)
    - Implement `release_buggy()` to mark buggy as available
    - Subscribe to `VIP_DETECTED`, `STATE_CHANGED`, and `BOARDING_ALERT` events
    - Emit `BUGGY_DISPATCHED` event after assignment
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 11.2, 11.3_

  - [ ]* 8.2 Write property test for buggy assignment with battery constraint
    - **Property 10: Buggy Assignment with Battery Constraint**
    - Test that only buggies with battery > 20% are assigned
    - **Validates: Requirements 4.1, 4.2**

  - [ ]* 8.3 Write property test for battery depletion
    - **Property 13: Battery Depletion Simulation**
    - Test that battery decreases by 5% per trip and buggies become unavailable below 20%
    - **Validates: Requirements 11.2, 11.3**

  - [ ]* 8.4 Write property test for buggy status updates
    - **Property 14: Buggy Status Update After Trip**
    - Test that buggies return to available status after trip completion
    - **Validates: Requirements 11.5**

- [ ] 9. Implement Lounge Agent
  - [x] 9.1 Create Lounge Agent with reservation management
    - Implement `create_reservation()` for VIP lounge pre-reservation
    - Implement capacity checking (max 50 VIPs from config)
    - Implement reservation queueing when at capacity
    - Implement `verify_lounge_entry()` with face recognition
    - Implement `grant_access()` to update occupancy and emit `LOUNGE_ENTRY` event
    - Implement `extend_reservation()` for flight delays
    - Implement `release_reservation()` to decrement occupancy
    - Subscribe to `VIP_DETECTED`, `FLIGHT_DELAY`, and face detection events
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 12.3, 12.4_

  - [ ]* 9.2 Write property test for lounge reservation creation
    - **Property 15: Lounge Reservation Creation**
    - Test that VIP detection triggers lounge reservation
    - **Validates: Requirements 5.1**

  - [ ]* 9.3 Write property test for lounge capacity queueing
    - **Property 16: Lounge Capacity Queueing**
    - Test that reservations are queued when at capacity
    - **Validates: Requirements 5.2**

  - [ ]* 9.4 Write property test for lounge access verification
    - **Property 17: Lounge Access Verification Workflow**
    - Test face verification and access granting workflow
    - **Validates: Requirements 5.3, 5.4**

  - [ ]* 9.5 Write property test for lounge occupancy tracking
    - **Property 18: Lounge Occupancy Tracking**
    - Test that occupancy increments/decrements correctly
    - **Validates: Requirements 5.5, 12.3, 12.4**

- [ ] 10. Implement Flight Intelligence Agent
  - [x] 10.1 Create Flight Intelligence Agent with monitoring
    - Implement `monitor_flights()` loop (check every 60 seconds)
    - Implement `check_boarding_time()` to emit `BOARDING_ALERT` 15 minutes before boarding
    - Implement `detect_delay()` to compare scheduled vs actual departure times
    - Emit `FLIGHT_DELAY` event with new departure time when delay detected
    - Emit `BOARDING_ALERT` event for all VIPs on the flight
    - Calculate boarding time as departure time - 30 minutes
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 10.2 Write property test for boarding alert timing
    - **Property 19: Boarding Alert Timing**
    - Test that boarding alerts are emitted 15 minutes before boarding
    - **Validates: Requirements 6.2, 14.4**

  - [ ]* 10.3 Write property test for flight delay event emission
    - **Property 20: Flight Delay Event Emission**
    - Test that delays trigger FLIGHT_DELAY events with correct data
    - **Validates: Requirements 6.3**

  - [ ]* 10.4 Write property test for flight boarding status transition
    - **Property 22: Flight Boarding Status Transition**
    - Test that boarding status triggers VIP state transitions
    - **Validates: Requirements 6.5**

- [ ] 11. Implement Baggage Agent
  - [x] 11.1 Create Baggage Agent with priority handling
    - Implement `generate_priority_tag()` for VIPs in CHECKED_IN state
    - Emit `BAGGAGE_PRIORITY_TAGGED` event after tag generation
    - Implement `simulate_baggage_routing()` with priority handling
    - Implement `track_loading_status()` to return current status
    - Log baggage completion time when reaching aircraft
    - Adjust priority on flight delays
    - Subscribe to `STATE_CHANGED` and `FLIGHT_DELAY` events
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 11.2 Write property test for priority baggage tag generation
    - **Property 23: Priority Baggage Tag Generation**
    - Test that CHECKED_IN state triggers tag generation and event emission
    - **Validates: Requirements 7.1, 7.2**

  - [ ]* 11.3 Write property test for baggage completion logging
    - **Property 24: Baggage Completion Logging**
    - Test that completion times are logged correctly
    - **Validates: Requirements 7.4**

  - [ ]* 11.4 Write property test for baggage priority adjustment
    - **Property 25: Baggage Priority Adjustment on Delay**
    - Test that flight delays adjust baggage priority
    - **Validates: Requirements 7.5**

- [x] 12. Checkpoint - Ensure all agents tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 13. Implement Master Orchestrator
  - [x] 13.1 Create Master Orchestrator with state machine
    - Implement state transition validation (enforce sequence: PREPARED → ARRIVED → BUGGY_PICKUP → CHECKED_IN → SECURITY_CLEARED → LOUNGE_ENTRY → BUGGY_TO_GATE → BOARDED → COMPLETED)
    - Implement `transition_state()` to validate and execute transitions
    - Implement `handle_vip_detected()` to transition PREPARED → ARRIVED
    - Implement `handle_flight_delay()` to extend lounge time and reschedule buggy
    - Implement `recover_workflows()` to restore active workflows from database on startup
    - Emit `STATE_CHANGED` event after successful transitions
    - Log rejected transitions with error messages
    - Release all resources when VIP reaches COMPLETED state
    - Subscribe to `VIP_DETECTED`, `FLIGHT_DELAY`, `BOARDING_ALERT` events
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 6.4, 15.4_

  - [ ]* 13.2 Write property test for state transition sequence enforcement
    - **Property 4: State Transition Sequence Enforcement**
    - Test that only valid state transitions are allowed
    - **Validates: Requirements 2.3, 2.4**

  - [ ]* 13.3 Write property test for state transition event emission
    - **Property 5: State Transition Event Emission**
    - Test that STATE_CHANGED events are emitted after transitions
    - **Validates: Requirements 2.2**

  - [ ]* 13.4 Write property test for VIP detection triggers arrival
    - **Property 6: VIP Detection Triggers Arrival**
    - Test that VIP_DETECTED transitions PREPARED → ARRIVED
    - **Validates: Requirements 2.1**

  - [ ]* 13.5 Write property test for workflow completion resource release
    - **Property 7: Workflow Completion Resource Release**
    - Test that COMPLETED state releases all resources
    - **Validates: Requirements 2.5, 3.5, 4.5**

  - [ ]* 13.6 Write property test for flight delay workflow adjustment
    - **Property 21: Flight Delay Workflow Adjustment**
    - Test that flight delays extend lounge time and reschedule buggy
    - **Validates: Requirements 6.4, 14.5**

- [ ] 14. Implement WebSocket Manager
  - [x] 14.1 Create WebSocket Manager for real-time communication
    - Implement `connect()` to accept new WebSocket connections
    - Implement `disconnect()` to handle client disconnections
    - Implement `broadcast()` to send messages to all connected clients
    - Implement `send_to_client()` for targeted messages
    - Define message format: `{type, payload, timestamp}`
    - Support message types: `vip_update`, `escort_update`, `buggy_update`, `lounge_update`, `flight_update`
    - Subscribe to all Event Bus events and push to WebSocket clients
    - Ensure updates are pushed within 500ms of event occurrence
    - _Requirements: 16.1, 16.2, 16.3, 16.5, 8.2_

  - [ ]* 14.2 Write property test for WebSocket update latency
    - **Property 26: WebSocket Update Latency**
    - Test that events are pushed to clients within 500ms
    - **Validates: Requirements 8.2**

- [ ] 15. Implement FastAPI backend main application
  - [x] 15.1 Create FastAPI app with REST endpoints
    - Create `/api/vips` endpoint to list all VIPs with current state
    - Create `/api/vips/{vip_id}` endpoint to get VIP details and timeline
    - Create `/api/escorts` endpoint to list all escorts with status
    - Create `/api/buggies` endpoint to list all buggies with battery and status
    - Create `/api/lounge` endpoint to get occupancy and reservations
    - Create `/api/flights` endpoint to list all flights with status
    - Create `/ws` WebSocket endpoint for real-time updates
    - Initialize all agents and orchestrator on startup
    - Connect Event Bus to WebSocket Manager
    - _Requirements: 8.1, 8.4, 9.1, 10.1, 11.1, 12.1, 18.2_

  - [ ]* 15.2 Write integration tests for REST endpoints
    - Test that all endpoints return correct data structure
    - Test error handling for invalid requests
    - _Requirements: 8.1, 9.1, 10.1, 11.1, 12.1_

- [ ] 16. Implement demo flow simulation
  - [x] 16.1 Create demo mode functionality
    - Implement demo trigger endpoint `/api/demo/start`
    - Simulate VIP arrival through face detection
    - Auto-progress through all workflow states with realistic delays (30s between states)
    - Simulate flight delay at LOUNGE_ENTRY state (add 30 min delay)
    - Simulate boarding alert 15 minutes before boarding
    - Display all dashboard updates in real-time
    - Implement demo reset endpoint `/api/demo/reset` to clear all VIP states and resource assignments
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5_

  - [ ]* 16.2 Write integration test for demo flow
    - Test complete demo flow from start to finish
    - Verify all state transitions occur in sequence
    - Verify all events are emitted correctly
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5_

- [x] 17. Checkpoint - Ensure backend integration tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 18. Implement React frontend - Dashboard page
  - [x] 18.1 Create Dashboard page with VIP cards
    - Create `Dashboard.tsx` component to display all active VIPs
    - Create `VIPCard.tsx` component showing VIP name, current state, escort, buggy, lounge status
    - Implement WebSocket connection to receive real-time updates
    - Update VIP cards in real-time when events occur (no manual refresh)
    - Implement click navigation to VIP details page
    - Apply dark theme with airport control room aesthetic (dark background, high contrast, monospace fonts for data)
    - Use color coding: green (active/available), yellow (in-progress), red (alerts/unavailable), blue (completed)
    - _Requirements: 8.1, 8.2, 8.3, 17.1, 17.2, 17.3, 17.4, 17.5_

  - [ ]* 18.2 Write property test for dashboard data completeness
    - **Property 27: Dashboard Data Completeness**
    - Test that all required data fields are present and accurate
    - **Validates: Requirements 8.4, 9.3, 9.4**

  - [ ]* 18.3 Write property test for real-time timeline updates
    - **Property 29: Real-Time Timeline Updates**
    - Test that new events appear in timeline without refresh
    - **Validates: Requirements 9.5**

- [ ] 19. Implement React frontend - VIP Details page
  - [x] 19.1 Create VIP Details page with timeline
    - Create `VIPDetails.tsx` component to display complete VIP journey
    - Display state transition timeline with timestamps
    - Display all service log entries in chronological order
    - Display face recognition confidence scores for detection events
    - Display current escort assignment, buggy assignment, lounge reservation status
    - Append new events to timeline in real-time via WebSocket
    - Apply consistent dark theme styling
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 17.1, 17.4, 17.5_

  - [ ]* 19.2 Write property test for service log chronological ordering
    - **Property 28: Service Log Chronological Ordering**
    - Test that service logs are displayed in chronological order
    - **Validates: Requirements 9.2**

- [ ] 20. Implement React frontend - Escort Management page
  - [x] 20.1 Create Escort Management page
    - Create `EscortManagement.tsx` component to display all escorts
    - Display escort name, status, current assignment, assignment history
    - Implement status filter: available, assigned, off-duty
    - Update escort display in real-time via WebSocket
    - Allow manual escort reassignment (optional feature)
    - Apply consistent dark theme styling
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 17.1, 17.4, 17.5_

  - [ ]* 20.2 Write property test for escort filtering correctness
    - **Property 30: Escort Filtering Correctness**
    - Test that filter displays only matching escorts
    - **Validates: Requirements 10.2**

- [ ] 21. Implement React frontend - Transport panel
  - [x] 21.1 Create Transport panel component
    - Create `TransportPanel.tsx` component to display buggy fleet
    - Display buggy ID, battery level, status, current assignment
    - Simulate battery depletion visualization (progress bar)
    - Display buggy location: idle, en_route_pickup, en_route_destination
    - Update buggy status in real-time via WebSocket
    - Show visual alert when battery < 20%
    - Apply consistent dark theme styling
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 17.1, 17.4, 17.5_

  - [ ]* 21.2 Write property test for real-time status updates
    - **Property 31: Real-Time Status Updates**
    - Test that resource status changes update dashboard in real-time
    - **Validates: Requirements 10.3, 11.5**

- [ ] 22. Implement React frontend - Lounge panel
  - [x] 22.1 Create Lounge panel component
    - Create `LoungePanel.tsx` component to display lounge status
    - Display current occupancy count and maximum capacity
    - Display all active reservations with VIP names and expected duration
    - Increment occupancy on LOUNGE_ENTRY events
    - Decrement occupancy on VIP departure
    - Display visual indicator (red/yellow) when occupancy > 80% of capacity
    - Update in real-time via WebSocket
    - Apply consistent dark theme styling
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 17.1, 17.4, 17.5_

  - [ ]* 22.2 Write property test for lounge occupancy indicator
    - **Property 32: Lounge Occupancy Indicator**
    - Test that visual indicator appears when occupancy > 80%
    - **Validates: Requirements 12.5**

- [ ] 23. Implement WebSocket client service
  - [x] 23.1 Create WebSocket client with reconnection logic
    - Create `websocketService.ts` to manage WebSocket connection
    - Implement connection establishment to `/ws` endpoint
    - Implement message parsing and event dispatching to React components
    - Implement reconnection with exponential backoff on connection loss
    - Handle all message types: `vip_update`, `escort_update`, `buggy_update`, `lounge_update`, `flight_update`
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

  - [ ]* 23.2 Write unit tests for WebSocket reconnection
    - Test reconnection logic with simulated connection failures
    - Test exponential backoff timing
    - _Requirements: 16.4_

- [x] 24. Checkpoint - Ensure frontend integration works
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 25. Final integration and end-to-end testing
  - [x] 25.1 Wire all components together
    - Verify Event Bus connects all agents
    - Verify Master Orchestrator coordinates workflow
    - Verify WebSocket Manager pushes updates to frontend
    - Verify database persistence for all operations
    - Verify demo flow works end-to-end
    - Test complete VIP journey: face detection → escort assignment → buggy dispatch → lounge entry → boarding alert → boarding → completion
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 13.1, 13.2, 13.3, 13.4, 13.5, 18.3, 18.4_

  - [ ]* 25.2 Write property test for event subscription registration
    - **Property 33: Event Subscription Registration**
    - Test that all agents register with Event Bus on initialization
    - **Validates: Requirements 13.1, 18.2**

  - [ ]* 25.3 Write end-to-end integration tests
    - Test complete VIP journey from arrival to boarding
    - Test flight delay scenario with workflow adjustments
    - Test resource exhaustion scenarios (no escorts, no buggies, lounge at capacity)
    - Test concurrent VIP processing (multiple VIPs simultaneously)
    - _Requirements: All requirements_

- [x] 26. Final checkpoint - Production readiness
  - Ensure all tests pass, ask the user if questions arise.
  - Verify error handling and logging throughout the system
  - Verify type hints are present in all Python code
  - Verify async/await patterns are used correctly
  - Verify environment variables are used for configuration
  - Review code quality and production readiness

## Notes

- Tasks marked with `*` are optional property-based tests and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties across all inputs
- Unit tests validate specific examples, edge cases, and error conditions
- The implementation follows a bottom-up approach: infrastructure → agents → orchestrator → frontend → integration
- Demo mode enables stakeholder demonstrations without requiring actual camera hardware
- WebSocket communication ensures sub-second latency for real-time dashboard updates
- The system uses Python type hints and async/await for production-ready code quality
