import { useEffect, useState } from 'react';
import { websocketService, ConnectionState } from '../services/websocketService';

/**
 * Escort Management Page Component
 * 
 * Displays all escorts with their current status, assignments, and assignment history.
 * Updates in real-time via WebSocket.
 * 
 * Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 17.1, 17.4, 17.5
 */

interface AssignedVIP {
  id: string;
  name: string;
  current_state: string;
}

interface EscortData {
  id: string;
  name: string;
  status: 'available' | 'assigned' | 'off_duty';
  assigned_vip: AssignedVIP | null;
  created_at: string;
}

type StatusFilter = 'all' | 'available' | 'assigned' | 'off_duty';

export const EscortManagement: React.FC = () => {
  const [escorts, setEscorts] = useState<EscortData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>(
    ConnectionState.DISCONNECTED
  );
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  // Fetch escorts data
  const fetchEscorts = async () => {
    try {
      setLoading(true);
      setError(null);

      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/escorts`);

      if (!response.ok) {
        throw new Error(`Failed to fetch escorts: ${response.statusText}`);
      }

      const data = await response.json();
      setEscorts(data);
    } catch (err) {
      console.error('Error fetching escorts:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch escorts');
    } finally {
      setLoading(false);
    }
  };

  // Initialize WebSocket connection and fetch initial data
  useEffect(() => {
    // Fetch initial data
    fetchEscorts();

    // Connect to WebSocket
    websocketService.connect();

    // Subscribe to connection state changes
    const unsubscribeState = websocketService.onStateChange((state) => {
      setConnectionState(state);
    });

    // Subscribe to escort updates
    const unsubscribeEscort = websocketService.subscribe('escort_update', (message) => {
      console.log('[EscortManagement] Received escort update:', message);
      // Refresh escort list when any escort update occurs
      fetchEscorts();
    });

    // Subscribe to VIP updates (affects escort assignments)
    const unsubscribeVIP = websocketService.subscribe('vip_update', (message) => {
      console.log('[EscortManagement] Received VIP update:', message);
      // Refresh escort list when VIP state changes (may affect assignments)
      fetchEscorts();
    });

    // Cleanup on unmount
    return () => {
      unsubscribeState();
      unsubscribeEscort();
      unsubscribeVIP();
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

  // Filter escorts by status
  const filteredEscorts = statusFilter === 'all'
    ? escorts
    : escorts.filter(escort => escort.status === statusFilter);

  // Get status counts
  const statusCounts = {
    all: escorts.length,
    available: escorts.filter(e => e.status === 'available').length,
    assigned: escorts.filter(e => e.status === 'assigned').length,
    off_duty: escorts.filter(e => e.status === 'off_duty').length,
  };

  // Get status color
  const getStatusColor = (status: string): string => {
    const statusColors: Record<string, string> = {
      'available': 'text-status-active',
      'assigned': 'text-status-progress',
      'off_duty': 'text-control-text-dim',
    };
    return statusColors[status] || 'text-control-text';
  };

  // Get status background color
  const getStatusBgColor = (status: string): string => {
    const statusBgColors: Record<string, string> = {
      'available': 'bg-status-active/10',
      'assigned': 'bg-status-progress/10',
      'off_duty': 'bg-control-text-dim/10',
    };
    return statusBgColors[status] || 'bg-control-panel';
  };

  // Format status for display
  const formatStatus = (status: string): string => {
    return status
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  // Format state for display
  const formatState = (state: string): string => {
    return state
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  // Format timestamp for display
  const formatTimestamp = (timestamp: string): string => {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="space-y-6">
      {/* Header Section */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-control-text">Escort Management</h2>
          <p className="text-control-text-dim mt-1">
            Monitor and manage escort assignments
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
          <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Total Escorts</p>
          <p className="text-3xl font-bold font-mono text-control-text">{statusCounts.all}</p>
        </div>
        <div className="bg-control-panel border border-control-border rounded-lg p-4">
          <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Available</p>
          <p className="text-3xl font-bold font-mono text-status-active">{statusCounts.available}</p>
        </div>
        <div className="bg-control-panel border border-control-border rounded-lg p-4">
          <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Assigned</p>
          <p className="text-3xl font-bold font-mono text-status-progress">{statusCounts.assigned}</p>
        </div>
        <div className="bg-control-panel border border-control-border rounded-lg p-4">
          <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Off Duty</p>
          <p className="text-3xl font-bold font-mono text-control-text-dim">{statusCounts.off_duty}</p>
        </div>
      </div>

      {/* Filter Buttons */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-control-text-dim mr-2">Filter by status:</span>
        {(['all', 'available', 'assigned', 'off_duty'] as StatusFilter[]).map((filter) => (
          <button
            key={filter}
            onClick={() => setStatusFilter(filter)}
            className={`px-4 py-2 rounded-lg text-sm font-mono transition-colors ${
              statusFilter === filter
                ? 'bg-status-active text-control-bg'
                : 'bg-control-panel border border-control-border text-control-text-dim hover:text-control-text hover:border-status-active/50'
            }`}
          >
            {formatStatus(filter)} ({statusCounts[filter]})
          </button>
        ))}
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
          <p className="text-control-text-dim mt-4">Loading escort data...</p>
        </div>
      )}

      {/* Escorts Grid */}
      {!loading && filteredEscorts.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredEscorts.map((escort) => (
            <div
              key={escort.id}
              className="bg-control-panel border border-control-border rounded-lg p-6 hover:border-status-active/30 transition-colors"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="text-3xl">👔</div>
                  <div>
                    <h3 className="text-lg font-bold text-control-text">{escort.name}</h3>
                    <p className="text-xs font-mono text-control-text-dim">
                      ID: {escort.id.slice(0, 8)}
                    </p>
                  </div>
                </div>
                <div className={`px-3 py-1 rounded ${getStatusBgColor(escort.status)}`}>
                  <span className={`text-sm font-mono font-semibold ${getStatusColor(escort.status)}`}>
                    {formatStatus(escort.status)}
                  </span>
                </div>
              </div>

              {/* Current Assignment */}
              <div className="space-y-3">
                <div className="border-t border-control-border pt-3">
                  <p className="text-xs text-control-text-dim uppercase tracking-wide mb-2">
                    Current Assignment
                  </p>
                  {escort.assigned_vip ? (
                    <div className="bg-control-bg rounded p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-mono text-control-text">
                          {escort.assigned_vip.name}
                        </span>
                        <span className="text-xs font-mono text-status-progress">
                          {formatState(escort.assigned_vip.current_state)}
                        </span>
                      </div>
                      <p className="text-xs font-mono text-control-text-dim">
                        VIP ID: {escort.assigned_vip.id.slice(0, 8)}
                      </p>
                    </div>
                  ) : (
                    <p className="text-sm text-control-text-dim italic">
                      {escort.status === 'available' ? 'Ready for assignment' : 'No active assignment'}
                    </p>
                  )}
                </div>

                {/* Metadata */}
                <div className="border-t border-control-border pt-3">
                  <p className="text-xs text-control-text-dim">
                    Created: {formatTimestamp(escort.created_at)}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && filteredEscorts.length === 0 && (
        <div className="text-center py-20 bg-control-panel border border-control-border rounded-lg">
          <div className="text-6xl mb-4">👔</div>
          <h3 className="text-xl font-bold text-control-text mb-2">
            No {statusFilter !== 'all' ? formatStatus(statusFilter) : ''} Escorts
          </h3>
          <p className="text-control-text-dim">
            {statusFilter !== 'all'
              ? `No escorts with status "${formatStatus(statusFilter)}" found`
              : 'No escorts available in the system'}
          </p>
        </div>
      )}
    </div>
  );
};
