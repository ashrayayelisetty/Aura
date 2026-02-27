import { useEffect, useState } from 'react';
import { websocketService } from '../services/websocketService';

/**
 * Lounge Panel Component
 * 
 * Displays lounge status with real-time updates via WebSocket.
 * Shows occupancy count, capacity, active reservations, and visual indicators.
 * Implements dark theme with airport control room aesthetic.
 * 
 * Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5, 17.1, 17.4, 17.5
 */

export interface LoungeReservation {
  id: string;
  vip: {
    id: string;
    name: string;
  } | null;
  status: string;
  reservation_time: string;
  entry_time: string | null;
  duration_minutes: number;
}

export interface LoungeData {
  occupancy: number;
  capacity: number;
  utilization_percent: number;
  reservations: LoungeReservation[];
}

/**
 * Get utilization color based on percentage
 * Red when > 80%, yellow when > 60%, green otherwise
 */
const getUtilizationColor = (percent: number): string => {
  if (percent > 80) return 'text-status-alert';
  if (percent > 60) return 'text-status-progress';
  return 'text-status-active';
};

/**
 * Get utilization background color for visual indicator
 */
const getUtilizationBgColor = (percent: number): string => {
  if (percent > 80) return 'bg-status-alert/10 border-status-alert';
  if (percent > 60) return 'bg-status-progress/10 border-status-progress';
  return 'bg-status-active/10 border-status-active';
};

/**
 * Get utilization bar color for progress bar
 */
const getUtilizationBarColor = (percent: number): string => {
  if (percent > 80) return 'bg-status-alert';
  if (percent > 60) return 'bg-status-progress';
  return 'bg-status-active';
};

/**
 * Format ISO timestamp to readable time
 */
const formatTime = (isoString: string | null): string => {
  if (!isoString) return 'N/A';
  
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      hour12: false 
    });
  } catch {
    return 'Invalid';
  }
};

/**
 * Calculate expected departure time based on entry time and duration
 */
const calculateDepartureTime = (entryTime: string | null, durationMinutes: number): string => {
  if (!entryTime) return 'Pending';
  
  try {
    const entry = new Date(entryTime);
    const departure = new Date(entry.getTime() + durationMinutes * 60000);
    return formatTime(departure.toISOString());
  } catch {
    return 'Invalid';
  }
};

/**
 * Get status badge color
 */
const getStatusColor = (status: string): string => {
  const statusColors: Record<string, string> = {
    'reserved': 'text-status-progress bg-status-progress/10',
    'active': 'text-status-active bg-status-active/10',
    'completed': 'text-status-complete bg-status-complete/10',
  };
  return statusColors[status] || 'text-control-text bg-control-panel';
};

export const LoungePanel: React.FC = () => {
  const [loungeData, setLoungeData] = useState<LoungeData>({
    occupancy: 0,
    capacity: 50,
    utilization_percent: 0,
    reservations: []
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch lounge data from API
  const fetchLoungeData = async () => {
    try {
      setError(null);
      
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/lounge`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch lounge data: ${response.statusText}`);
      }
      
      const data = await response.json();
      setLoungeData(data);
    } catch (err) {
      console.error('Error fetching lounge data:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch lounge data');
    } finally {
      setLoading(false);
    }
  };

  // Initialize data and WebSocket subscription
  useEffect(() => {
    // Fetch initial data
    fetchLoungeData();

    // Subscribe to lounge updates via WebSocket
    const unsubscribe = websocketService.subscribe('lounge_update', (message) => {
      console.log('[LoungePanel] Received lounge update:', message);
      
      // Refresh lounge data when any lounge update occurs
      fetchLoungeData();
    });

    // Cleanup on unmount
    return () => {
      unsubscribe();
    };
  }, []);

  const { occupancy, capacity, utilization_percent, reservations } = loungeData;
  const availableSpaces = capacity - occupancy;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-bold text-control-text">VIP Lounge</h3>
          <p className="text-sm text-control-text-dim mt-1">
            Real-time occupancy and reservation monitoring
          </p>
        </div>
        
        {/* High Utilization Alert */}
        {utilization_percent > 80 && (
          <div className="flex items-center gap-2 px-3 py-2 bg-status-alert/10 border border-status-alert rounded-lg">
            <span className="text-status-alert text-lg">⚠</span>
            <span className="text-sm font-mono text-status-alert">
              High Occupancy
            </span>
          </div>
        )}
      </div>

      {/* Occupancy Stats */}
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-control-panel border border-control-border rounded-lg p-3">
          <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Occupancy</p>
          <p className={`text-2xl font-bold font-mono ${getUtilizationColor(utilization_percent)}`}>
            {occupancy}/{capacity}
          </p>
        </div>
        <div className="bg-control-panel border border-control-border rounded-lg p-3">
          <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Utilization</p>
          <p className={`text-2xl font-bold font-mono ${getUtilizationColor(utilization_percent)}`}>
            {utilization_percent}%
          </p>
        </div>
        <div className="bg-control-panel border border-control-border rounded-lg p-3">
          <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Available</p>
          <p className="text-2xl font-bold font-mono text-status-active">{availableSpaces}</p>
        </div>
        <div className="bg-control-panel border border-control-border rounded-lg p-3">
          <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Reservations</p>
          <p className="text-2xl font-bold font-mono text-control-text">{reservations.length}</p>
        </div>
      </div>

      {/* Utilization Progress Bar */}
      <div className={`p-4 rounded-lg border ${getUtilizationBgColor(utilization_percent)}`}>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-mono text-control-text">Capacity Utilization</span>
          <span className={`text-sm font-bold font-mono ${getUtilizationColor(utilization_percent)}`}>
            {utilization_percent}%
          </span>
        </div>
        <div className="w-full bg-control-border rounded-full h-3 overflow-hidden">
          <div
            className={`h-full ${getUtilizationBarColor(utilization_percent)} transition-all duration-300`}
            style={{ width: `${utilization_percent}%` }}
          />
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
          <p className="text-control-text-dim mt-3 text-sm">Loading lounge data...</p>
        </div>
      )}

      {/* Active Reservations */}
      {!loading && reservations.length > 0 && (
        <div>
          <h4 className="text-lg font-bold text-control-text mb-3">
            Active Reservations ({reservations.length})
          </h4>
          <div className="space-y-2">
            {reservations.map((reservation) => (
              <div
                key={reservation.id}
                className="bg-control-panel border border-control-border rounded-lg p-4 hover:border-control-border/80 transition-colors"
              >
                <div className="flex items-start justify-between">
                  {/* VIP Info */}
                  <div className="flex items-center gap-3">
                    <div className="text-2xl">👤</div>
                    <div>
                      <h5 className="text-base font-bold font-mono text-control-text">
                        {reservation.vip?.name || 'Unknown VIP'}
                      </h5>
                      <div className={`inline-block px-2 py-0.5 rounded text-xs font-mono font-semibold ${getStatusColor(reservation.status)} mt-1`}>
                        {reservation.status.toUpperCase()}
                      </div>
                    </div>
                  </div>

                  {/* Duration */}
                  <div className="text-right">
                    <p className="text-sm font-mono text-control-text">
                      {reservation.duration_minutes} min
                    </p>
                    <p className="text-xs text-control-text-dim">Duration</p>
                  </div>
                </div>

                {/* Timing Info */}
                <div className="grid grid-cols-3 gap-4 mt-3 pt-3 border-t border-control-border">
                  <div>
                    <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">
                      Reserved
                    </p>
                    <p className="text-sm font-mono text-control-text">
                      {formatTime(reservation.reservation_time)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">
                      Entry
                    </p>
                    <p className="text-sm font-mono text-control-text">
                      {formatTime(reservation.entry_time)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">
                      Expected Exit
                    </p>
                    <p className="text-sm font-mono text-control-text">
                      {calculateDepartureTime(reservation.entry_time, reservation.duration_minutes)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!loading && reservations.length === 0 && (
        <div className="text-center py-12 bg-control-panel border border-control-border rounded-lg">
          <div className="text-4xl mb-3">🛋️</div>
          <h4 className="text-lg font-bold text-control-text mb-2">No Active Reservations</h4>
          <p className="text-control-text-dim text-sm">
            Lounge reservations will appear here
          </p>
        </div>
      )}
    </div>
  );
};
