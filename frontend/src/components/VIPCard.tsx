import { useNavigate } from 'react-router-dom';

/**
 * VIP Card Component
 * 
 * Displays a VIP card with current state, escort, buggy, and lounge status.
 * Implements click navigation to VIP details page.
 * 
 * Validates: Requirements 8.1, 8.3, 17.1, 17.2, 17.3, 17.4, 17.5
 */

export interface VIPData {
  id: string;
  name: string;
  flight_id: string;
  current_state: string;
  escort: {
    id: string;
    name: string;
  } | null;
  buggy: {
    id: string;
    battery_level: number;
  } | null;
  lounge: {
    id: string;
    status: string;
  } | null;
  created_at: string;
  updated_at: string;
}

interface VIPCardProps {
  vip: VIPData;
}

/**
 * Get color class for VIP state
 * Color coding: green (active/available), yellow (in-progress), red (alerts/unavailable), blue (completed)
 */
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

/**
 * Get background color class for VIP state
 */
const getStateBgColor = (state: string): string => {
  const stateBgColors: Record<string, string> = {
    'prepared': 'bg-control-text-dim/10',
    'arrived': 'bg-status-active/10',
    'buggy_pickup': 'bg-status-progress/10',
    'checked_in': 'bg-status-progress/10',
    'security_cleared': 'bg-status-progress/10',
    'lounge_entry': 'bg-status-active/10',
    'buggy_to_gate': 'bg-status-progress/10',
    'boarded': 'bg-status-progress/10',
    'completed': 'bg-status-complete/10',
  };
  return stateBgColors[state] || 'bg-control-panel';
};

/**
 * Format state name for display
 */
const formatState = (state: string): string => {
  return state
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

/**
 * Get battery level color
 */
const getBatteryColor = (level: number): string => {
  if (level > 50) return 'text-status-active';
  if (level > 20) return 'text-status-progress';
  return 'text-status-alert';
};

export const VIPCard: React.FC<VIPCardProps> = ({ vip }) => {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate(`/vip/${vip.id}`);
  };

  return (
    <div
      onClick={handleClick}
      className="bg-control-panel border border-control-border rounded-lg p-6 hover:border-status-active/50 transition-colors cursor-pointer"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-xl font-bold text-control-text mb-1">{vip.name}</h3>
          <p className="text-sm font-mono text-control-text-dim">
            Flight: {vip.flight_id}
          </p>
        </div>
        <div className={`px-3 py-1 rounded ${getStateBgColor(vip.current_state)}`}>
          <span className={`text-sm font-mono font-semibold ${getStateColor(vip.current_state)}`}>
            {formatState(vip.current_state)}
          </span>
        </div>
      </div>

      {/* Status Grid */}
      <div className="grid grid-cols-3 gap-4">
        {/* Escort Status */}
        <div className="space-y-1">
          <p className="text-xs text-control-text-dim uppercase tracking-wide">Escort</p>
          {vip.escort ? (
            <div>
              <p className="text-sm font-mono text-status-active">✓ Assigned</p>
              <p className="text-xs text-control-text-dim truncate">{vip.escort.name}</p>
            </div>
          ) : (
            <p className="text-sm font-mono text-control-text-dim">Pending</p>
          )}
        </div>

        {/* Buggy Status */}
        <div className="space-y-1">
          <p className="text-xs text-control-text-dim uppercase tracking-wide">Buggy</p>
          {vip.buggy ? (
            <div>
              <p className="text-sm font-mono text-status-active">✓ Assigned</p>
              <p className={`text-xs font-mono ${getBatteryColor(vip.buggy.battery_level)}`}>
                Battery: {vip.buggy.battery_level}%
              </p>
            </div>
          ) : (
            <p className="text-sm font-mono text-control-text-dim">Pending</p>
          )}
        </div>

        {/* Lounge Status */}
        <div className="space-y-1">
          <p className="text-xs text-control-text-dim uppercase tracking-wide">Lounge</p>
          {vip.lounge ? (
            <div>
              <p className="text-sm font-mono text-status-active">
                {vip.lounge.status === 'active' ? '✓ Active' : '○ Reserved'}
              </p>
              <p className="text-xs text-control-text-dim capitalize">{vip.lounge.status}</p>
            </div>
          ) : (
            <p className="text-sm font-mono text-control-text-dim">Pending</p>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-control-border">
        <p className="text-xs text-control-text-dim">
          ID: <span className="font-mono">{vip.id}</span>
        </p>
      </div>
    </div>
  );
};
