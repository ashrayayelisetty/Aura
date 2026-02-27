import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { websocketService, ConnectionState } from '../services/websocketService';

/**
 * VIP Details Page Component
 * 
 * Displays complete VIP journey with state transition timeline and service logs.
 * Updates in real-time via WebSocket.
 * 
 * Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 17.1, 17.4, 17.5
 */

interface TimelineEvent {
  id: string;
  event_type: string;
  event_data: Record<string, any>;
  timestamp: string;
  agent_source: string;
}

interface VIPDetails {
  id: string;
  name: string;
  flight_id: string;
  current_state: string;
  escort: {
    id: string;
    name: string;
    status: string;
  } | null;
  buggy: {
    id: string;
    battery_level: number;
    status: string;
    current_location: string;
  } | null;
  lounge: {
    id: string;
    status: string;
    reservation_time: string;
    entry_time: string | null;
    exit_time: string | null;
    duration_minutes: number;
  } | null;
  flight: {
    id: string;
    departure_time: string;
    boarding_time: string;
    status: string;
    gate: string;
    destination: string;
    delay_minutes: number;
  } | null;
  timeline: TimelineEvent[];
  created_at: string;
  updated_at: string;
}

export const VIPDetails: React.FC = () => {
  const { vip_id } = useParams<{ vip_id: string }>();
  const navigate = useNavigate();
  const [vipDetails, setVipDetails] = useState<VIPDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>(
    ConnectionState.DISCONNECTED
  );

  // Fetch VIP details
  const fetchVIPDetails = async () => {
    if (!vip_id) return;

    try {
      setLoading(true);
      setError(null);

      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/vips/${vip_id}`);

      if (!response.ok) {
        throw new Error(`Failed to fetch VIP details: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      setVipDetails(data);
    } catch (err) {
      console.error('Error fetching VIP details:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch VIP details');
    } finally {
      setLoading(false);
    }
  };

  // Initialize WebSocket connection and fetch initial data
  useEffect(() => {
    fetchVIPDetails();

    // Connect to WebSocket
    websocketService.connect();

    // Subscribe to connection state changes
    const unsubscribeState = websocketService.onStateChange((state) => {
      setConnectionState(state);
    });

    // Subscribe to VIP updates - refresh when this VIP is updated
    const unsubscribeVIP = websocketService.subscribe('vip_update', (message) => {
      if (message.payload.vip_id === vip_id) {
        console.log('[VIPDetails] Received update for this VIP:', message);
        fetchVIPDetails();
      }
    });

    // Cleanup on unmount
    return () => {
      unsubscribeState();
      unsubscribeVIP();
    };
  }, [vip_id]);

  // Format timestamp for display
  const formatTimestamp = (timestamp: string): string => {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  // Format event type for display
  const formatEventType = (eventType: string): string => {
    return eventType
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  // Get color for event type
  const getEventColor = (eventType: string): string => {
    const eventColors: Record<string, string> = {
      'vip_detected': 'text-status-active',
      'state_changed': 'text-status-progress',
      'escort_assigned': 'text-status-active',
      'buggy_dispatched': 'text-status-active',
      'lounge_reserved': 'text-status-active',
      'lounge_entry': 'text-status-active',
      'flight_delay': 'text-status-alert',
      'boarding_alert': 'text-status-progress',
      'baggage_priority_tagged': 'text-status-active',
    };
    return eventColors[eventType] || 'text-control-text';
  };

  // Get icon for event type
  const getEventIcon = (eventType: string): string => {
    const eventIcons: Record<string, string> = {
      'vip_detected': '👤',
      'state_changed': '🔄',
      'escort_assigned': '👔',
      'buggy_dispatched': '🚗',
      'lounge_reserved': '🛋️',
      'lounge_entry': '🚪',
      'flight_delay': '⏰',
      'boarding_alert': '📢',
      'baggage_priority_tagged': '🧳',
    };
    return eventIcons[eventType] || '•';
  };

  // Get state color
  const getStateColor = (state: string): string => {
    const stateColors: Record<string, string> = {
      'prepared': 'text-control-text-dim',
      'arrived': 'text-status-active',
      'buggy_pickup': 'text-status-progress',
      'checked_in': 'text-status-progress',
      'security_cleared': 'text-status-progress',
      'lounge_entry': 'text-status-active',
      'buggy_to_gate': 'text-status-progress',
      'boarded': 'text-status-progress',
      'completed': 'text-status-complete',
    };
    return stateColors[state] || 'text-control-text';
  };

  // Format state name
  const formatState = (state: string): string => {
    return state
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  // Get battery color
  const getBatteryColor = (level: number): string => {
    if (level > 50) return 'text-status-active';
    if (level > 20) return 'text-status-progress';
    return 'text-status-alert';
  };

  if (loading) {
    return (
      <div className="text-center py-20">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-status-active"></div>
        <p className="text-control-text-dim mt-4">Loading VIP details...</p>
      </div>
    );
  }

  if (error || !vipDetails) {
    return (
      <div className="space-y-6">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 text-control-text-dim hover:text-control-text transition-colors"
        >
          <span>←</span>
          <span>Back to Dashboard</span>
        </button>
        <div className="bg-status-alert/10 border border-status-alert rounded-lg p-6">
          <p className="text-status-alert font-mono">
            ⚠ {error || 'VIP not found'}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back Button */}
      <button
        onClick={() => navigate('/')}
        className="flex items-center gap-2 text-control-text-dim hover:text-control-text transition-colors"
      >
        <span>←</span>
        <span>Back to Dashboard</span>
      </button>

      {/* Header Section */}
      <div className="bg-control-panel border border-control-border rounded-lg p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold text-control-text mb-2">
              {vipDetails.name}
            </h1>
            <div className="flex items-center gap-4 text-sm text-control-text-dim">
              <span className="font-mono">ID: {vipDetails.id}</span>
              <span>•</span>
              <span className="font-mono">Flight: {vipDetails.flight_id}</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className={`px-4 py-2 rounded bg-${getStateColor(vipDetails.current_state).replace('text-', '')}/10`}>
              <span className={`text-sm font-mono font-semibold ${getStateColor(vipDetails.current_state)}`}>
                {formatState(vipDetails.current_state)}
              </span>
            </div>
            <div className="flex items-center gap-2 px-3 py-2 bg-control-bg border border-control-border rounded">
              <div className={`w-2 h-2 rounded-full ${
                connectionState === ConnectionState.CONNECTED ? 'bg-status-active' : 'bg-status-alert'
              } animate-pulse`} />
              <span className="text-xs font-mono text-control-text-dim">
                {connectionState === ConnectionState.CONNECTED ? 'Live' : 'Offline'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Flight Information */}
      {vipDetails.flight && (
        <div className="bg-control-panel border border-control-border rounded-lg p-6">
          <h2 className="text-xl font-bold text-control-text mb-4">Flight Information</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Destination</p>
              <p className="text-lg font-mono text-control-text">{vipDetails.flight.destination}</p>
            </div>
            <div>
              <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Gate</p>
              <p className="text-lg font-mono text-control-text">{vipDetails.flight.gate}</p>
            </div>
            <div>
              <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Departure</p>
              <p className="text-sm font-mono text-control-text">
                {formatTimestamp(vipDetails.flight.departure_time)}
              </p>
            </div>
            <div>
              <p className="text-xs text-control-text-dim uppercase tracking-wide mb-1">Status</p>
              <p className={`text-sm font-mono font-semibold ${
                vipDetails.flight.status === 'delayed' ? 'text-status-alert' : 'text-status-active'
              }`}>
                {vipDetails.flight.status.toUpperCase()}
                {vipDetails.flight.delay_minutes > 0 && ` (+${vipDetails.flight.delay_minutes}m)`}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Current Assignments */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Escort Assignment */}
        <div className="bg-control-panel border border-control-border rounded-lg p-6">
          <h3 className="text-sm text-control-text-dim uppercase tracking-wide mb-3">
            Escort Assignment
          </h3>
          {vipDetails.escort ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-2xl">👔</span>
                <span className="text-lg font-mono text-control-text">
                  {vipDetails.escort.name}
                </span>
              </div>
              <p className="text-sm font-mono text-status-active">
                Status: {vipDetails.escort.status}
              </p>
              <p className="text-xs text-control-text-dim font-mono">
                ID: {vipDetails.escort.id}
              </p>
            </div>
          ) : (
            <p className="text-control-text-dim">No escort assigned</p>
          )}
        </div>

        {/* Buggy Assignment */}
        <div className="bg-control-panel border border-control-border rounded-lg p-6">
          <h3 className="text-sm text-control-text-dim uppercase tracking-wide mb-3">
            Buggy Assignment
          </h3>
          {vipDetails.buggy ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-2xl">🚗</span>
                <span className="text-lg font-mono text-control-text">
                  Buggy {vipDetails.buggy.id.slice(0, 8)}
                </span>
              </div>
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-control-text-dim">Battery</span>
                  <span className={`text-sm font-mono font-semibold ${getBatteryColor(vipDetails.buggy.battery_level)}`}>
                    {vipDetails.buggy.battery_level}%
                  </span>
                </div>
                <div className="w-full bg-control-bg rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${
                      vipDetails.buggy.battery_level > 50 ? 'bg-status-active' :
                      vipDetails.buggy.battery_level > 20 ? 'bg-status-progress' :
                      'bg-status-alert'
                    }`}
                    style={{ width: `${vipDetails.buggy.battery_level}%` }}
                  />
                </div>
              </div>
              <p className="text-sm font-mono text-control-text-dim">
                Location: {vipDetails.buggy.current_location.replace('_', ' ')}
              </p>
            </div>
          ) : (
            <p className="text-control-text-dim">No buggy assigned</p>
          )}
        </div>

        {/* Lounge Reservation */}
        <div className="bg-control-panel border border-control-border rounded-lg p-6">
          <h3 className="text-sm text-control-text-dim uppercase tracking-wide mb-3">
            Lounge Reservation
          </h3>
          {vipDetails.lounge ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-2xl">🛋️</span>
                <span className={`text-lg font-mono font-semibold ${
                  vipDetails.lounge.status === 'active' ? 'text-status-active' : 'text-status-progress'
                }`}>
                  {vipDetails.lounge.status.toUpperCase()}
                </span>
              </div>
              <div className="space-y-1 text-sm">
                <p className="text-control-text-dim">
                  Reserved: {formatTimestamp(vipDetails.lounge.reservation_time)}
                </p>
                {vipDetails.lounge.entry_time && (
                  <p className="text-control-text-dim">
                    Entered: {formatTimestamp(vipDetails.lounge.entry_time)}
                  </p>
                )}
                <p className="text-control-text-dim">
                  Duration: {vipDetails.lounge.duration_minutes} minutes
                </p>
              </div>
            </div>
          ) : (
            <p className="text-control-text-dim">No lounge reservation</p>
          )}
        </div>
      </div>

      {/* Timeline Section */}
      <div className="bg-control-panel border border-control-border rounded-lg p-6">
        <h2 className="text-xl font-bold text-control-text mb-6">Journey Timeline</h2>
        
        {vipDetails.timeline.length === 0 ? (
          <p className="text-control-text-dim text-center py-8">No events recorded yet</p>
        ) : (
          <div className="space-y-4">
            {vipDetails.timeline.map((event, index) => (
              <div
                key={event.id}
                className="flex gap-4 pb-4 border-b border-control-border last:border-b-0 last:pb-0"
              >
                {/* Timeline indicator */}
                <div className="flex flex-col items-center">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-xl ${
                    index === vipDetails.timeline.length - 1 ? 'bg-status-active/20' : 'bg-control-bg'
                  }`}>
                    {getEventIcon(event.event_type)}
                  </div>
                  {index < vipDetails.timeline.length - 1 && (
                    <div className="w-0.5 h-full bg-control-border mt-2" />
                  )}
                </div>

                {/* Event details */}
                <div className="flex-1 pt-2">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h3 className={`font-mono font-semibold ${getEventColor(event.event_type)}`}>
                        {formatEventType(event.event_type)}
                      </h3>
                      <p className="text-xs text-control-text-dim font-mono mt-1">
                        {formatTimestamp(event.timestamp)}
                      </p>
                    </div>
                    <span className="text-xs text-control-text-dim font-mono px-2 py-1 bg-control-bg rounded">
                      {event.agent_source}
                    </span>
                  </div>

                  {/* Event data */}
                  {Object.keys(event.event_data).length > 0 && (
                    <div className="mt-3 bg-control-bg rounded p-3 space-y-1">
                      {Object.entries(event.event_data).map(([key, value]) => (
                        <div key={key} className="flex items-start gap-2 text-sm">
                          <span className="text-control-text-dim font-mono">{key}:</span>
                          <span className="text-control-text font-mono flex-1">
                            {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
