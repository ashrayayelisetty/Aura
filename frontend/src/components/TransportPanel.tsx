import { useEffect, useState } from 'react';
import { websocketService } from '../services/websocketService';

/**
 * Transport Panel Component
 * 
 * Displays buggy fleet status with real-time updates via WebSocket.
 * Shows battery levels, status, assignments, and location.
 * Implements dark theme with airport control room aesthetic.
 * 
 * Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5, 17.1, 17.4, 17.5
 */

export interface BuggyData {
  id: string;
  battery_level: number;
  status: string;
  current_location: string;
  assigned_vip: {
    id: string;
    name: string;
    current_state: string;
  } | null;
  created_at: string;
}

/**
 * Get color class for buggy status
 */
const getStatusColor = (status: string): string => {
  const statusColors: Record<string, string> = {
    'available': 'text-status-active',
    'assigned': 'text-status-progress',
    'charging': 'text-status-progress',
    'maintenance': 'text-status-alert',
  };
  return statusColors[status] || 'text-control-text';
};

/**
 * Get background color class for buggy status
 */
const getStatusBgColor = (status: string): string => {
  const statusBgColors: Record<string, string> = {
    'available': 'bg-status-active/10',
    'assigned': 'bg-status-progress/10',
    'charging': 'bg-status-progress/10',
    'maintenance': 'bg-status-alert/10',
  };
  return statusBgColors[status] || 'bg-control-panel';
};

/**
 * Get battery level color based on percentage
 * Alert (red) when < 20%, warning (yellow) when < 50%, good (green) otherwise
 */
const getBatteryColor = (level: number): string => {
  if (level < 20) return 'text-status-alert';
  if (level < 50) return 'text-status-progress';
  return 'text-status-active';
};

/**
 * Get battery bar color for progress bar
 */
const getBatteryBarColor = (level: number): string => {
  if (level < 20) return 'bg-status-alert';
  if (level < 50) return 'bg-status-progress';
  return 'bg-status-active';
};

/**
 * Format location for display
 */
const formatLocation = (location: string): string => {
  return location
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

/**
 * Get location icon
 */
const getLocationIcon = (location: string): string => {
  const icons: Record<string, string> = {
    'idle': '○',
    'en_route_pickup': '→',
    'en_route_destination': '⇒',
  };
  return icons[location] || '○';
};

export const TransportPanel: React.FC = () => {
  const [buggies, setBuggies] = useState<BuggyData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch buggy data from API
  const fetchBuggies = async () => {
    try {
      setError(null);
      
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/buggies`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch buggies: ${response.statusText}`);
      }
      
      const data = await response.json();
      setBuggies(data);
    } catch (err) {
      console.error('Error fetching buggies:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch buggies');
    } finally {
      setLoading(false);
    }
  };

  // Initialize data and WebSocket subscription
  useEffect(() => {
    // Fetch initial data
    fetchBuggies();

    // Subscribe to buggy updates via WebSocket
    const unsubscribe = websocketService.subscribe('buggy_update', (message) => {
      console.log('[TransportPanel] Received buggy update:', message);
      
      // Refresh buggy list when any buggy update occurs
      fetchBuggies();
    });

    // Cleanup on unmount
    return () => {
      unsubscribe();
    };
  }, []);

  // Calculate fleet statistics
  const availableBuggies = buggies.filter(b => b.status === 'available').length;
  const assignedBuggies = buggies.filter(b => b.status === 'assigned').length;
  const lowBatteryBuggies = buggies.filter(b => b.battery_level < 20).length;
  const avgBattery = buggies.length > 0
    ? Math.round(buggies.reduce((sum, b) => sum + b.battery_level, 0) / buggies.length)
    : 0;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-bold text-control-text">Transport Fleet</h3>
          <p className="text-sm text-control-text-dim mt-1">
            Real-time buggy status and battery monitoring
          </p>
        </div>
        
        {/* Low Battery Alert */}
        {lowBatteryBuggies > 0 && (
          <div className="flex items-center gap-2 px-3 py-2 bg-status-alert/10 border border-status-alert rounded-lg">
            <span className="text-status-alert text-lg">⚠</span>
            <span className="text-sm font-mono text-status-alert">
              {lowBatteryBuggies} Low Battery
            </span>
          </div>
        )}
      </div>

      {/* Fleet Stats */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-control-panel border border-control-border rounded-lg p-3">
          <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Total Fleet</p>
          <p className="text-2xl font-bold font-mono text-control-text">{buggies.length}</p>
        </div>
        <div className="bg-control-panel border border-control-border rounded-lg p-3">
          <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Available</p>
          <p className="text-2xl font-bold font-mono text-status-active">{availableBuggies}</p>
        </div>
        <div className="bg-control-panel border border-control-border rounded-lg p-3">
          <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">In Use</p>
          <p className="text-2xl font-bold font-mono text-status-progress">{assignedBuggies}</p>
        </div>
        <div className="bg-control-panel border border-control-border rounded-lg p-3">
          <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Avg Battery</p>
          <p className={`text-2xl font-bold font-mono ${getBatteryColor(avgBattery)}`}>
            {avgBattery}%
          </p>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-status-alert/10 border border-status-alert rounded-lg p-3">
          <p className="text-status-alert font-mono text-sm">
            ⚠ {error}
          </p>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-status-active"></div>
          <p className="text-control-text-dim mt-3 text-sm">Loading fleet data...</p>
        </div>
      )}

      {/* Buggy List */}
      {!loading && buggies.length > 0 && (
        <div className="grid grid-cols-1 gap-3">
          {buggies.map((buggy) => (
            <div
              key={buggy.id}
              className="bg-control-panel border border-control-border rounded-lg p-4 hover:border-control-border/80 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                {/* Buggy ID and Status */}
                <div className="flex items-center gap-3">
                  <div className="text-2xl">🚗</div>
                  <div>
                    <h4 className="text-lg font-bold font-mono text-control-text">
                      {buggy.id}
                    </h4>
                    <div className={`inline-block px-2 py-0.5 rounded text-xs font-mono font-semibold ${getStatusBgColor(buggy.status)} ${getStatusColor(buggy.status)} mt-1`}>
                      {buggy.status.toUpperCase()}
                    </div>
                  </div>
                </div>

                {/* Battery Level with Alert */}
                <div className="text-right">
                  <div className="flex items-center gap-2">
                    {buggy.battery_level < 20 && (
                      <span className="text-status-alert text-lg">⚠</span>
                    )}
                    <span className={`text-2xl font-bold font-mono ${getBatteryColor(buggy.battery_level)}`}>
                      {buggy.battery_level}%
                    </span>
                  </div>
                  <p className="text-xs text-control-text-dim mt-1">Battery Level</p>
                </div>
              </div>

              {/* Battery Progress Bar */}
              <div className="mb-3">
                <div className="w-full bg-control-border rounded-full h-2 overflow-hidden">
                  <div
                    className={`h-full ${getBatteryBarColor(buggy.battery_level)} transition-all duration-300`}
                    style={{ width: `${buggy.battery_level}%` }}
                  />
                </div>
              </div>

              {/* Location and Assignment Info */}
              <div className="grid grid-cols-2 gap-4">
                {/* Location */}
                <div>
                  <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">
                    Location
                  </p>
                  <div className="flex items-center gap-2">
                    <span className="text-control-text">{getLocationIcon(buggy.current_location)}</span>
                    <span className="text-sm font-mono text-control-text">
                      {formatLocation(buggy.current_location)}
                    </span>
                  </div>
                </div>

                {/* Assignment */}
                <div>
                  <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">
                    Assignment
                  </p>
                  {buggy.assigned_vip ? (
                    <div>
                      <p className="text-sm font-mono text-status-active">
                        ✓ {buggy.assigned_vip.name}
                      </p>
                      <p className="text-xs text-control-text-dim capitalize">
                        {buggy.assigned_vip.current_state.replace(/_/g, ' ')}
                      </p>
                    </div>
                  ) : (
                    <p className="text-sm font-mono text-control-text-dim">
                      Unassigned
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && buggies.length === 0 && (
        <div className="text-center py-12 bg-control-panel border border-control-border rounded-lg">
          <div className="text-4xl mb-3">🚗</div>
          <h4 className="text-lg font-bold text-control-text mb-2">No Buggies Available</h4>
          <p className="text-control-text-dim text-sm">
            Fleet information will appear here
          </p>
        </div>
      )}
    </div>
  );
};
