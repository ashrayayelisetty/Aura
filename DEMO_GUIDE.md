# AURA-VIP System Demo Guide

## Overview

The AURA-VIP system is a fully functional airport VIP orchestration platform with real-time monitoring and automated workflow management. This guide explains what's implemented, what's simulated, and how to demonstrate the system.

## What's Fully Implemented

### ✅ Backend Architecture
- **Event-Driven Multi-Agent System**: 6 specialized agents (Identity, Escort, Transport, Lounge, Flight Intelligence, Baggage)
- **Master Orchestrator**: State machine managing VIP workflow lifecycle
- **Event Bus**: Pub/sub system for agent communication with retry logic
- **WebSocket Manager**: Real-time updates to frontend (sub-500ms latency)
- **REST API**: Complete CRUD operations for all resources
- **Database**: SQLite with SQLAlchemy ORM, proper indexing
- **Rule Engine**: Centralized business logic

### ✅ Frontend Dashboard
- **Real-Time Updates**: WebSocket connection with automatic reconnection
- **VIP Cards**: Live status updates without page refresh
- **Transport Panel**: Buggy fleet monitoring with battery visualization
- **Lounge Panel**: Occupancy tracking and reservation management
- **Escort Management**: Staff assignment and availability tracking
- **VIP Details**: Complete journey timeline with service logs
- **Dark Theme**: Airport control room aesthetic

### ✅ Core Features
- **State Machine**: Enforced workflow sequence (9 states)
- **Resource Management**: Automatic escort and buggy assignment
- **Lounge Reservations**: Capacity management and queueing
- **Flight Monitoring**: Delay detection and workflow adjustment
- **Priority Baggage**: Automatic tagging for VIPs
- **Service Logging**: Complete audit trail of all events

## What's Simulated (Demo Mode)

### 🎭 Face Recognition
**Status**: Capability implemented, camera integration simulated

- **What's Real**: DeepFace library integrated, face embedding extraction works, similarity matching implemented
- **What's Simulated**: No actual camera feed - demo mode creates VIPs with random embeddings
- **For Production**: Would connect to airport security cameras via RTSP/ONVIF protocols

### 🎭 VIP Detection
**Status**: Event-driven workflow works, trigger is simulated

- **What's Real**: VIP_DETECTED event triggers complete workflow, all agents respond correctly
- **What's Simulated**: Demo mode manually emits VIP_DETECTED event instead of camera detection
- **For Production**: Identity Agent would process camera frames at 2 FPS and emit events automatically

### 🎭 Buggy Movement
**Status**: Dispatch logic works, physical movement simulated

- **What's Real**: Battery depletion (5% per trip), availability checking, assignment logic
- **What's Simulated**: Trip duration and location updates are time-based simulations
- **For Production**: Would integrate with buggy GPS/IoT devices for real-time tracking

### 🎭 Flight Data
**Status**: Monitoring logic works, data source simulated

- **What's Real**: Delay detection, boarding alerts, workflow adjustments
- **What's Simulated**: Flight data is manually created, not from real flight APIs
- **For Production**: Would integrate with airport FIDS (Flight Information Display System) or airline APIs

## How to Run the Demo

### Prerequisites
- Python 3.10+ with all dependencies installed
- Node.js 18+ with frontend dependencies installed
- Both backend and frontend servers running

### Step 1: Initialize the System

```bash
# From project root
python -m backend.database.init_db
```

This creates:
- 5 escorts (Alice, Bob, Carol, David, Emma)
- 3 buggies (85%, 92%, 67% battery)
- 2 flights (BA123 to London, EK456 to Dubai)
- 3 sample VIP profiles

### Step 2: Start Backend

```bash
python -m backend.main
```

Watch for:
```
INFO: AURA-VIP System startup complete
INFO: Uvicorn running on http://0.0.0.0:8000
```

### Step 3: Start Frontend

```bash
cd frontend
npm run dev
```

Open browser to `http://localhost:5173`

### Step 4: Run Demo

**Option A: From Dashboard UI**
1. Click "▶ Start Demo" button
2. Watch VIP card appear and update every 30 seconds
3. Scroll down to see Transport and Lounge panels update
4. Click VIP card to see detailed timeline
5. Click "⟲ Reset Demo" to clear and start over

**Option B: From PowerShell**
```powershell
# Start demo
Invoke-WebRequest -Uri http://localhost:8000/api/demo/start -Method POST -UseBasicParsing

# Reset demo
Invoke-WebRequest -Uri http://localhost:8000/api/demo/reset -Method POST -UseBasicParsing
```

## Demo Timeline

When you start the demo, here's what happens:

| Time | Event | What You'll See |
|------|-------|-----------------|
| t=0s | Demo VIP Created | VIP card appears with "PREPARED" state |
| t=2s | VIP Detection | State changes to "ARRIVED", escort assigned |
| t=2s | Buggy Dispatch | Buggy assigned, battery shown in Transport Panel |
| t=32s | Buggy Pickup | State changes to "BUGGY_PICKUP" |
| t=62s | Check-In | State changes to "CHECKED_IN", baggage tagged |
| t=92s | Security | State changes to "SECURITY_CLEARED" |
| t=122s | Lounge Entry | State changes to "LOUNGE_ENTRY", occupancy increases |
| t=152s | Flight Delay | 30-minute delay announced, lounge time extended |
| t=182s | Boarding Alert | Alert issued, buggy dispatched to gate |
| t=212s | Buggy to Gate | State changes to "BUGGY_TO_GATE" |
| t=242s | Boarded | State changes to "BOARDED" |
| t=272s | Completed | State changes to "COMPLETED", resources released |

## What to Show Stakeholders

### 1. Real-Time Monitoring
- Open dashboard and start demo
- Point out that updates happen automatically without refresh
- Show WebSocket connection indicator (green = connected)

### 2. Resource Management
- Scroll to Transport Panel - show buggy battery levels
- Scroll to Lounge Panel - show occupancy tracking
- Navigate to Escorts page - show staff assignments

### 3. Complete Journey Tracking
- Click any VIP card
- Show complete timeline with timestamps
- Point out service logs from different agents

### 4. Event-Driven Architecture
- Open browser console (F12)
- Show WebSocket messages being received
- Point out different event types (vip_update, escort_update, buggy_update, lounge_update)

### 5. Workflow Management
- Show state progression in VIP card
- Explain state machine enforcement
- Demonstrate flight delay handling

## API Endpoints for Testing

```bash
# Health check
curl http://localhost:8000/api/health

# List all VIPs
curl http://localhost:8000/api/vips

# Get VIP details
curl http://localhost:8000/api/vips/{vip_id}

# List escorts
curl http://localhost:8000/api/escorts

# List buggies
curl http://localhost:8000/api/buggies

# Lounge status
curl http://localhost:8000/api/lounge

# List flights
curl http://localhost:8000/api/flights
```

## Production Readiness

### What's Ready for Production
- ✅ Event-driven architecture scales horizontally
- ✅ WebSocket manager handles multiple clients
- ✅ Database schema with proper indexing
- ✅ Error handling and logging throughout
- ✅ Type hints and async/await patterns
- ✅ 226 passing tests (100% success rate)

### What Needs Production Integration
- 🔧 Camera integration for face recognition
- 🔧 Airport FIDS API for real flight data
- 🔧 Buggy IoT/GPS integration for real-time tracking
- 🔧 Lounge access control hardware integration
- 🔧 Authentication and authorization
- 🔧 Production database (PostgreSQL)
- 🔧 Load balancing and horizontal scaling
- 🔧 Monitoring and alerting (Prometheus/Grafana)

## Troubleshooting

### Frontend Not Updating
1. Check WebSocket connection indicator (should be green)
2. Open browser console - look for WebSocket errors
3. Verify backend is running on port 8000
4. Check CORS settings in backend/main.py

### No Escorts/Buggies Showing
1. Run database initialization: `python -m backend.database.init_db`
2. Refresh browser
3. Check API directly: `curl http://localhost:8000/api/escorts`

### Demo Not Starting
1. Reset demo first: Click "⟲ Reset Demo"
2. Check backend logs for errors
3. Verify database is accessible
4. Try API directly: `Invoke-WebRequest -Uri http://localhost:8000/api/demo/start -Method POST`

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  Dashboard │ VIP Details │ Escorts │ Transport │ Lounge     │
└────────────────────────┬────────────────────────────────────┘
                         │ WebSocket + REST API
┌────────────────────────┴────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Master Orchestrator                      │  │
│  │         (State Machine + Workflow Manager)            │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                    │
│  ┌──────────────────────┴───────────────────────────────┐  │
│  │                   Event Bus                           │  │
│  │         (Pub/Sub with Retry Logic)                    │  │
│  └──┬────┬────┬────┬────┬────┬────────────────────────┬─┘  │
│     │    │    │    │    │    │                        │    │
│  ┌──┴─┐┌─┴─┐┌─┴─┐┌─┴─┐┌─┴─┐┌─┴──┐              ┌─────┴──┐ │
│  │Iden││Esc││Tra││Lou││Fli││Bag │              │WebSock │ │
│  │tity││ort││nsp││nge││ght││gage│              │Manager │ │
│  │    ││   ││ort││   ││Int││    │              │        │ │
│  └────┘└───┘└───┘└───┘└───┘└────┘              └────────┘ │
│                         │                                    │
│  ┌──────────────────────┴───────────────────────────────┐  │
│  │              Database (SQLite/PostgreSQL)             │  │
│  │  VIPs │ Escorts │ Buggies │ Flights │ Logs │ Lounge  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Next Steps for Production

1. **Camera Integration**: Connect to airport security camera network
2. **Flight API**: Integrate with airline/airport FIDS systems
3. **IoT Integration**: Connect to buggy GPS and lounge access control
4. **Authentication**: Implement OAuth2/JWT for API security
5. **Scaling**: Deploy with Kubernetes for horizontal scaling
6. **Monitoring**: Add Prometheus metrics and Grafana dashboards
7. **Testing**: Add end-to-end tests with Playwright/Cypress
8. **Documentation**: API documentation with OpenAPI/Swagger

## Support

For questions or issues:
- Check backend logs: Look for ERROR or WARNING messages
- Check frontend console: Open browser DevTools (F12)
- Verify all services running: Backend (port 8000), Frontend (port 5173)
- Review test results: `cd backend && pytest -v`
