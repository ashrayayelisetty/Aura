import { useEffect, useState } from 'react';
import { VIPCard, VIPData } from '../components/VIPCard';
import { TransportPanel } from '../components/TransportPanel';
import { LoungePanel } from '../components/LoungePanel';
import { EventLogPanel } from '../components/EventLogPanel';
import { AgentStatusPanel } from '../components/AgentStatusPanel';
import { SystemMetricsPanel } from '../components/SystemMetricsPanel';
import { websocketService, ConnectionState } from '../services/websocketService';

/**
 * Dashboard Page Component
 * 
 * Displays all active VIPs with real-time updates via WebSocket.
 * Implements dark theme with airport control room aesthetic.
 * 
 * Validates: Requirements 8.1, 8.2, 8.3, 17.1, 17.2, 17.3, 17.4, 17.5
 */

export const Dashboard: React.FC = () => {
  const [vips, setVips] = useState<VIPData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>(
    ConnectionState.DISCONNECTED
  );
  const [demoStatus, setDemoStatus] = useState<string | null>(null);
  const [demoLoading, setDemoLoading] = useState(false);

  // Fetch initial VIP data
  const fetchVIPs = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/vips`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch VIPs: ${response.statusText}`);
      }
      
      const data = await response.json();
      setVips(data);
    } catch (err) {
      console.error('Error fetching VIPs:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch VIPs');
    } finally {
      setLoading(false);
    }
  };

  // Initialize WebSocket connection and fetch initial data
  useEffect(() => {
    // Fetch initial data
    fetchVIPs();

    // Connect to WebSocket
    websocketService.connect();

    // Subscribe to connection state changes
    const unsubscribeState = websocketService.onStateChange((state) => {
      setConnectionState(state);
    });

    // Subscribe to VIP updates
    const unsubscribeVIP = websocketService.subscribe('vip_update', (message) => {
      console.log('[Dashboard] Received VIP update:', message);
      fetchVIPs();
    });

    // Subscribe to escort updates (affects VIP card display)
    const unsubscribeEscort = websocketService.subscribe('escort_update', (message) => {
      console.log('[Dashboard] Received escort update:', message);
      fetchVIPs();
    });

    // Subscribe to buggy updates (affects VIP card display)
    const unsubscribeBuggy = websocketService.subscribe('buggy_update', (message) => {
      console.log('[Dashboard] Received buggy update:', message);
      fetchVIPs();
    });

    // Subscribe to lounge updates (affects VIP card display)
    const unsubscribeLounge = websocketService.subscribe('lounge_update', (message) => {
      console.log('[Dashboard] Received lounge update:', message);
      fetchVIPs();
    });

    // Cleanup on unmount
    return () => {
      unsubscribeState();
      unsubscribeVIP();
      unsubscribeEscort();
      unsubscribeBuggy();
      unsubscribeLounge();
    };
  }, []);

  // Get connection status indicator
  const getConnectionIndicator = () => {
    const indicators: Record<ConnectionState, { color: string; text: string }> = {
      [ConnectionState.CONNECTED]: { color: 'bg-status-active', text: 'Connected' },
      [ConnectionState.CONNECTING]: { color: 'bg-status-progress', text: 'Connecting...' },
      [ConnectionState.RECONNECTING]: { color: 'bg-status-progress', text: 'Reconnecting...' },
      [ConnectionState.DISCONNECTED]: { color: 'bg-status-alert', text: 'Disconnected' },
    };
    
    return indicators[connectionState] || indicators[ConnectionState.DISCONNECTED];
  };

  const connectionIndicator = getConnectionIndicator();

  // Filter VIPs by state
  const activeVIPs = vips.filter(vip => vip.current_state !== 'completed');
  const completedVIPs = vips.filter(vip => vip.current_state === 'completed');

  // Demo control functions
  const startDemo = async () => {
    try {
      setDemoLoading(true);
      setDemoStatus(null);
      
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/demo/start`, {
        method: 'POST',
      });
      
      if (!response.ok) {
        throw new Error(`Failed to start demo: ${response.statusText}`);
      }
      
      const data = await response.json();
      setDemoStatus(`Demo started! VIP ${data.vip_id} will progress through all states.`);
      
      // Refresh VIP list after a short delay
      setTimeout(() => fetchVIPs(), 1000);
    } catch (err) {
      console.error('Error starting demo:', err);
      setDemoStatus(`Error: ${err instanceof Error ? err.message : 'Failed to start demo'}`);
    } finally {
      setDemoLoading(false);
    }
  };

  const resetDemo = async () => {
    try {
      setDemoLoading(true);
      setDemoStatus(null);
      
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/demo/reset`, {
        method: 'POST',
      });
      
      if (!response.ok) {
        throw new Error(`Failed to reset demo: ${response.statusText}`);
      }
      
      const data = await response.json();
      setDemoStatus('Demo reset! All VIP states and resources cleared.');
      
      // Refresh VIP list
      fetchVIPs();
    } catch (err) {
      console.error('Error resetting demo:', err);
      setDemoStatus(`Error: ${err instanceof Error ? err.message : 'Failed to reset demo'}`);
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Section */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-control-text">VIP Dashboard</h2>
          <p className="text-control-text-dim mt-1">
            Real-time monitoring of all VIP journeys
          </p>
        </div>
        
        {/* Connection Status */}
        <div className="flex items-center gap-2 px-4 py-2 bg-control-panel border border-control-border rounded-lg">
          <div className={`w-2 h-2 rounded-full ${connectionIndicator.color} animate-pulse`} />
          <span className="text-sm font-mono text-control-text-dim">
            {connectionIndicator.text}
          </span>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-control-panel border border-control-border rounded-lg p-4">
          <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Total VIPs</p>
          <p className="text-3xl font-bold font-mono text-control-text">{vips.length}</p>
        </div>
        <div className="bg-control-panel border border-control-border rounded-lg p-4">
          <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Active</p>
          <p className="text-3xl font-bold font-mono text-status-active">{activeVIPs.length}</p>
        </div>
        <div className="bg-control-panel border border-control-border rounded-lg p-4">
          <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Completed</p>
          <p className="text-3xl font-bold font-mono text-status-complete">{completedVIPs.length}</p>
        </div>
        <div className="bg-control-panel border border-control-border rounded-lg p-4">
          <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">In Transit</p>
          <p className="text-3xl font-bold font-mono text-status-progress">
            {vips.filter(v => v.current_state.includes('buggy')).length}
          </p>
        </div>
      </div>

      {/* Demo Controls */}
      <div className="bg-control-panel border border-control-border rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-lg font-bold text-control-text">Demo Controls</h3>
            <p className="text-sm text-control-text-dim mt-1">
              Start or reset the VIP journey simulation
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={startDemo}
              disabled={demoLoading}
              className="px-4 py-2 bg-status-active hover:bg-status-active/80 text-control-bg font-mono font-semibold rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {demoLoading ? 'Starting...' : '▶ Start Demo'}
            </button>
            <button
              onClick={resetDemo}
              disabled={demoLoading}
              className="px-4 py-2 bg-status-alert hover:bg-status-alert/80 text-control-bg font-mono font-semibold rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {demoLoading ? 'Resetting...' : '⟲ Reset Demo'}
            </button>
          </div>
        </div>
        {demoStatus && (
          <div className="mt-3 p-3 bg-control-bg border border-control-border rounded text-sm font-mono text-control-text">
            {demoStatus}
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-status-alert/10 border border-status-alert rounded-lg p-4">
          <p className="text-status-alert font-mono text-sm">
            ⚠ {error}
          </p>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-status-active"></div>
          <p className="text-control-text-dim mt-4">Loading VIP data...</p>
        </div>
      )}

      {/* Active VIPs Section */}
      {!loading && activeVIPs.length > 0 && (
        <div>
          <h3 className="text-xl font-bold text-control-text mb-4">
            Active VIPs ({activeVIPs.length})
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {activeVIPs.map((vip) => (
              <VIPCard key={vip.id} vip={vip} />
            ))}
          </div>
        </div>
      )}

      {/* Completed VIPs Section */}
      {!loading && completedVIPs.length > 0 && (
        <div>
          <h3 className="text-xl font-bold text-control-text mb-4">
            Completed ({completedVIPs.length})
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {completedVIPs.map((vip) => (
              <VIPCard key={vip.id} vip={vip} />
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!loading && vips.length === 0 && (
        <div className="text-center py-20 bg-control-panel border border-control-border rounded-lg">
          <div className="text-6xl mb-4">✈️</div>
          <h3 className="text-xl font-bold text-control-text mb-2">No VIPs Currently</h3>
          <p className="text-control-text-dim">
            VIP cards will appear here when guests arrive
          </p>
        </div>
      )}

      {/* Transport Fleet Panel */}
      <div className="mt-8">
        <TransportPanel />
      </div>

      {/* Lounge Panel */}
      <div className="mt-8">
        <LoungePanel />
      </div>

      {/* System Monitoring Section */}
      <div className="mt-8">
        <h2 className="text-2xl font-bold text-control-text mb-4">System Monitoring</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Agent Status */}
          <AgentStatusPanel />
          
          {/* System Metrics */}
          <SystemMetricsPanel />
        </div>
      </div>

      {/* Event Log */}
      <div className="mt-8">
        <EventLogPanel />
      </div>
    </div>
  );
};
