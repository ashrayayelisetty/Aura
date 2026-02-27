import { useEffect, useState, useRef } from 'react';
import { websocketService } from '../services/websocketService';

/**
 * Event Log Panel Component
 * 
 * Displays real-time event stream showing backend agent activities.
 * Makes backend processing visible and convincing for demos.
 */

export interface LogEntry {
  id: string;
  timestamp: string;
  agent: string;
  level: 'info' | 'success' | 'warning' | 'error' | 'processing';
  message: string;
  details?: any;
}

const getAgentIcon = (agent: string): string => {
  const icons: Record<string, string> = {
    'identity': '🎥',
    'escort': '👤',
    'transport': '🚗',
    'lounge': '🛋️',
    'flight_intelligence': '✈️',
    'baggage': '🧳',
    'master_orchestrator': '🎯',
    'event_bus': '📢',
    'database': '💾',
    'websocket': '🔌',
    'demo_mode': '🎬',
  };
  return icons[agent.toLowerCase()] || '⚙️';
};

const getLevelColor = (level: string): string => {
  const colors: Record<string, string> = {
    'info': 'text-control-text-dim',
    'success': 'text-status-active',
    'warning': 'text-status-progress',
    'error': 'text-status-alert',
    'processing': 'text-blue-400',
  };
  return colors[level] || 'text-control-text';
};

const getLevelBadge = (level: string): string => {
  const badges: Record<string, string> = {
    'info': 'ℹ️',
    'success': '✅',
    'warning': '⚠️',
    'error': '❌',
    'processing': '⚡',
  };
  return badges[level] || '•';
};

export const EventLogPanel: React.FC = () => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isPaused, setIsPaused] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const maxLogs = 100; // Keep last 100 logs

  useEffect(() => {
    // Subscribe to all message types to capture activity
    const unsubscribers = [
      websocketService.subscribe('vip_update', (message) => {
        if (!isPaused) {
          addLog({
            agent: message.payload.source_agent,
            level: 'success',
            message: formatEventMessage(message.payload.event_type, message.payload),
            details: message.payload,
          });
        }
      }),
      websocketService.subscribe('escort_update', (message) => {
        if (!isPaused) {
          addLog({
            agent: message.payload.source_agent,
            level: 'success',
            message: formatEventMessage(message.payload.event_type, message.payload),
            details: message.payload,
          });
        }
      }),
      websocketService.subscribe('buggy_update', (message) => {
        if (!isPaused) {
          addLog({
            agent: message.payload.source_agent,
            level: 'success',
            message: formatEventMessage(message.payload.event_type, message.payload),
            details: message.payload,
          });
        }
      }),
      websocketService.subscribe('lounge_update', (message) => {
        if (!isPaused) {
          addLog({
            agent: message.payload.source_agent,
            level: 'success',
            message: formatEventMessage(message.payload.event_type, message.payload),
            details: message.payload,
          });
        }
      }),
      websocketService.subscribe('flight_update', (message) => {
        if (!isPaused) {
          addLog({
            agent: message.payload.source_agent,
            level: 'success',
            message: formatEventMessage(message.payload.event_type, message.payload),
            details: message.payload,
          });
        }
      }),
    ];

    return () => {
      unsubscribers.forEach(unsub => unsub());
    };
  }, [isPaused]);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const addLog = (entry: Omit<LogEntry, 'id' | 'timestamp'>) => {
    const newLog: LogEntry = {
      id: `${Date.now()}-${Math.random()}`,
      timestamp: new Date().toISOString(),
      ...entry,
    };

    setLogs(prev => {
      const updated = [...prev, newLog];
      // Keep only last maxLogs entries
      return updated.slice(-maxLogs);
    });
  };

  const formatEventMessage = (eventType: string, payload: any): string => {
    const messages: Record<string, (p: any) => string> = {
      'vip_detected': (p) => `Face detected! Confidence: ${(p.confidence * 100).toFixed(1)}% - VIP identified`,
      'state_changed': (p) => `VIP state transition: ${p.old_state?.toUpperCase()} → ${p.new_state?.toUpperCase()}`,
      'escort_assigned': (p) => `Escort assigned: ${p.escort_name || 'Staff member'} → VIP`,
      'buggy_dispatched': (p) => `Buggy dispatched: ${p.buggy_id || 'Vehicle'} (Battery: ${p.battery_level || 'N/A'}%)`,
      'lounge_reserved': (p) => `Lounge reservation created for VIP`,
      'lounge_entry': (p) => `VIP entered lounge - Occupancy updated`,
      'flight_delay': (p) => `Flight delay detected: +${p.delay_minutes || 0} minutes`,
      'boarding_alert': (p) => `Boarding alert issued for flight ${p.flight_id || 'N/A'}`,
      'baggage_priority_tagged': (p) => `Priority baggage tag generated`,
    };

    const formatter = messages[eventType];
    return formatter ? formatter(payload) : `Event: ${eventType}`;
  };

  const formatTime = (isoString: string): string => {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', { 
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const clearLogs = () => {
    setLogs([]);
  };

  return (
    <div className="bg-control-panel border border-control-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-control-border bg-control-bg">
        <div>
          <h3 className="text-lg font-bold text-control-text">System Activity Log</h3>
          <p className="text-xs text-control-text-dim mt-1">
            Real-time agent processing and event stream
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`px-3 py-1 text-xs font-mono rounded ${
              autoScroll 
                ? 'bg-status-active text-control-bg' 
                : 'bg-control-panel border border-control-border text-control-text'
            }`}
          >
            {autoScroll ? '📜 Auto-scroll ON' : '📜 Auto-scroll OFF'}
          </button>
          <button
            onClick={() => setIsPaused(!isPaused)}
            className={`px-3 py-1 text-xs font-mono rounded ${
              isPaused 
                ? 'bg-status-progress text-control-bg' 
                : 'bg-control-panel border border-control-border text-control-text'
            }`}
          >
            {isPaused ? '▶ Resume' : '⏸ Pause'}
          </button>
          <button
            onClick={clearLogs}
            className="px-3 py-1 text-xs font-mono rounded bg-control-panel border border-control-border text-control-text hover:bg-control-border"
          >
            🗑️ Clear
          </button>
        </div>
      </div>

      {/* Log Container */}
      <div 
        ref={logContainerRef}
        className="h-96 overflow-y-auto p-4 space-y-2 font-mono text-sm bg-black/20"
      >
        {logs.length === 0 ? (
          <div className="text-center py-12 text-control-text-dim">
            <div className="text-4xl mb-3">📊</div>
            <p>Waiting for system activity...</p>
            <p className="text-xs mt-2">Events will appear here in real-time</p>
          </div>
        ) : (
          logs.map((log) => (
            <div
              key={log.id}
              className="flex items-start gap-3 p-2 rounded hover:bg-control-panel/50 transition-colors"
            >
              {/* Timestamp */}
              <span className="text-control-text-dim text-xs whitespace-nowrap">
                {formatTime(log.timestamp)}
              </span>

              {/* Agent Icon */}
              <span className="text-lg">{getAgentIcon(log.agent)}</span>

              {/* Level Badge */}
              <span className="text-sm">{getLevelBadge(log.level)}</span>

              {/* Agent Name */}
              <span className="text-status-active font-semibold min-w-[120px]">
                {log.agent.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
              </span>

              {/* Message */}
              <span className={`flex-1 ${getLevelColor(log.level)}`}>
                {log.message}
              </span>
            </div>
          ))
        )}
      </div>

      {/* Footer Stats */}
      <div className="flex items-center justify-between p-3 border-t border-control-border bg-control-bg text-xs">
        <span className="text-control-text-dim">
          {logs.length} events logged
        </span>
        <span className="text-control-text-dim">
          {isPaused ? '⏸ Paused' : '🔴 Live'}
        </span>
      </div>
    </div>
  );
};
