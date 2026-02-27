# AURA-VIP Quick Start Guide

## 🚀 Get the Demo Running in 3 Minutes

### Step 1: Start Backend (Terminal 1)
```bash
# From project root
python -m backend.main
```

Wait for:
```
INFO: AURA-VIP System startup complete
INFO: Uvicorn running on http://0.0.0.0:8000
```

### Step 2: Start Frontend (Terminal 2)
```bash
cd frontend
npm run dev
```

Wait for:
```
VITE ready in XXX ms
Local: http://localhost:5173/
```

### Step 3: Open Browser
Navigate to: `http://localhost:5173`

### Step 4: Run Demo
Click the **"▶ Start Demo"** button on the dashboard

## 🎯 What You'll See

### Immediately:
1. **VIP Card** appears showing "Demo VIP Guest"
2. **Event Log** starts scrolling with agent activities
3. **Agent Status Panel** shows agents lighting up
4. **System Metrics** start updating

### Over 1 Minute:
- VIP progresses through 9 states (every 5-6 seconds)
- Escorts get assigned
- Buggies get dispatched (watch battery deplete!)
- Lounge occupancy increases
- Flight delay occurs
- Boarding alert triggers
- Resources get released

**Total demo time: ~50 seconds**

### Key Panels to Watch:

1. **Event Log** (bottom of page):
   - Shows every backend operation
   - Face recognition steps
   - Agent decision-making
   - Database queries

2. **Agent Status** (middle of page):
   - 6 agents lighting up when active
   - Event counters increasing
   - Last activity timestamps

3. **System Metrics** (middle of page):
   - Events per second
   - Response times
   - WebSocket latency
   - System uptime

4. **Transport Panel** (scroll down):
   - 3 buggies with battery levels
   - Watch battery deplete during trips
   - Status changes (available → assigned)

5. **Lounge Panel** (scroll down):
   - Occupancy counter
   - Capacity utilization
   - Active reservations

## 🎬 For Presentations

### Opening Line:
"Let me show you AURA-VIP - an AI-powered airport VIP orchestration system with a multi-agent architecture. Watch the Event Log to see the backend processing in real-time."

### During Demo:
1. Click "Start Demo"
2. **Point to Event Log**: "See the Identity Agent detecting the face, extracting features, comparing against the database"
3. **Point to Agent Status**: "Watch the agents light up as they process events"
4. **Point to System Metrics**: "Real-time performance - 2-3 events per second, sub-50ms response times"
5. **Scroll to Transport**: "Buggy battery management - depletes 5% per trip"
6. **Scroll to Lounge**: "Occupancy tracking in real-time"
7. **Click VIP Card**: "Complete journey timeline with all events"

### Key Message:
"This isn't a mockup - every line in the Event Log is a real backend operation. The agents are making decisions, querying the database, and coordinating via the Event Bus."

## 🔧 Troubleshooting

### Backend Won't Start
```bash
# Check if port 8000 is in use
netstat -ano | findstr :8000

# Kill the process if needed
taskkill /PID <PID> /F

# Restart backend
python -m backend.main
```

### Frontend Won't Start
```bash
# Check if port 5173 is in use
netstat -ano | findstr :5173

# Kill the process if needed
taskkill /PID <PID> /F

# Restart frontend
cd frontend
npm run dev
```

### No Escorts/Buggies Showing
```bash
# Initialize database
python -m backend.database.init_db

# Refresh browser
```

### Event Log Not Updating
1. Check WebSocket connection indicator (top right) - should be green
2. Open browser console (F12) - look for WebSocket errors
3. Restart both backend and frontend

## 📊 Demo Statistics

After running the demo, you can show:
- **226 passing tests** (run `cd backend && pytest -v`)
- **6 specialized agents** working together
- **9 state transitions** in the VIP workflow
- **Sub-50ms response times** on average
- **Real-time WebSocket updates** (sub-500ms latency)

## 🎯 Success Checklist

After the demo, stakeholders should understand:
- ✅ Real multi-agent AI system
- ✅ Event-driven architecture
- ✅ Real-time processing and coordination
- ✅ Production-ready design
- ✅ Sophisticated backend logic

## 📚 Additional Resources

- **Full Demo Guide**: [DEMO_GUIDE.md](DEMO_GUIDE.md)
- **Presentation Script**: [PRESENTATION_GUIDE.md](PRESENTATION_GUIDE.md)
- **What's New**: [WHATS_NEW.md](WHATS_NEW.md)
- **Technical Details**: [README.md](README.md)

## 💡 Pro Tips

1. **Let the Event Log scroll** for 10-15 seconds before talking - let them see the processing
2. **Use the pause button** if they have questions
3. **Show the browser console** (F12) for extra credibility - WebSocket messages
4. **Mention the numbers** - "226 tests", "6 agents", "512-dimensional embeddings"
5. **Click the VIP card** to show the complete timeline

## 🎬 Closing

"AURA-VIP demonstrates a production-ready, event-driven, multi-agent AI system. The face recognition, resource allocation, and workflow management are all real. For production, we'd integrate with airport cameras, flight APIs, and IoT devices - but the core system is fully functional."

---

**Need help?** Check the logs:
- Backend: Look at the terminal running `python -m backend.main`
- Frontend: Open browser console (F12)
- Tests: Run `cd backend && pytest -v`
