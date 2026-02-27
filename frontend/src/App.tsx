import { Routes, Route, Link, useLocation } from 'react-router-dom'
import { Dashboard } from './pages/Dashboard'
import { VIPDetails } from './pages/VIPDetails'
import { EscortManagement } from './pages/EscortManagement'

function App() {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-control-bg">
      <header className="bg-control-panel border-b border-control-border px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-control-text">
              AURA-VIP Command Dashboard
            </h1>
            <p className="text-sm text-control-text-dim mt-1">
              Autonomous Unified Responsive Airport – VIP Orchestrator
            </p>
          </div>
          
          {/* Navigation */}
          <nav className="flex items-center gap-2">
            <Link
              to="/"
              className={`px-4 py-2 rounded-lg text-sm font-mono transition-colors ${
                location.pathname === '/'
                  ? 'bg-status-active text-control-bg'
                  : 'text-control-text-dim hover:text-control-text hover:bg-control-bg'
              }`}
            >
              Dashboard
            </Link>
            <Link
              to="/escorts"
              className={`px-4 py-2 rounded-lg text-sm font-mono transition-colors ${
                location.pathname === '/escorts'
                  ? 'bg-status-active text-control-bg'
                  : 'text-control-text-dim hover:text-control-text hover:bg-control-bg'
              }`}
            >
              Escorts
            </Link>
          </nav>
        </div>
      </header>
      
      <main className="container mx-auto px-6 py-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/vip/:vip_id" element={<VIPDetails />} />
          <Route path="/escorts" element={<EscortManagement />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
