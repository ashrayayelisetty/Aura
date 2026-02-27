import { useEffect, useState } from 'react';
import { websocketService } from '../services/websocketService';

/**
 * Agent Status Panel Component
 * 
 * Displays real-time status of all backend agents.
 * Shows which agents are active, idle, or processing.
 */

interface AgentStatus {
  name: string;
  displayName: string;
  icon: string;
  status: 'idle' | 'processing' | 'active' | 'error';
  lastActivity: string | null;
  activityCount: number;
}

const initialAgents: AgentStatus[] = [
  { name: 'identity', displayName: 'Identity Agent', icon: '🎥', status: 'idle', lastActivity: null, activityCount: 0 },
  { name: 'escort', displayName: 'Escort Agent', icon: '👤', status: 'idle', lastActivity: null, activityCount: 0 },
  { name: 'transport', displayName: 'Transport Agent', icon: '🚗', status: 'idle', lastActivity: null, activityCount: 0 },
  { name: 'lounge', displayName: 'Lounge Agent', icon: '🛋️', status: 'idle', lastActivity: null, activityCount: 0 },
  { name: 'flight_intelligence', displayName: 'Flight Intelligence', icon: '✈️', status: 'idle', lastActivity: null, activityCount: 0 },
  { name: 'baggage', displayName: 'Baggage Agent', icon: '🧳', status: 'idle', lastActivity: null, activityCount: 0 },
];

const getStatusColor = (status: string): string => {
  const colors: Record<string, string> = {
    'idle': 'text-control-text-dim',
    'processing': 'text-status-progress',
    'active': 'text-status-active',
    'error': 'text-status-alert',
  };
  return colors[status] || 'text-control-text';
};

const getStatusBg = (status: string): string => {
  const colors: Record<string, string> = {
    'idle': 'bg-control-border',
    'processing': 'bg-status-progress',
    'active': 'bg-status-active',
    'error': 'bg-status-alert',
  };
  return colors[status] || 'bg-control-border';
};

const getStatusLabel = (status: string): string => {
  const labels: Record<string, string> = {
    'idle': 'IDLE',
    'processing': 'PROCESSING',
    'active': 'ACTIVE',
    'error': 'ERROR',
  };
  return labels[status] || 'UNKNOWN';
};

export const AgentStatusPanel: React.FC = () => {
  const [agents, setAgents] = useState<AgentStatus[]>(initialAgents);

  useEffect(() => {
    // Subscribe to ALL WebSocket messages to track agent activity
    const handleMessage = (message: any) => {
      const sourceAgent = message.payload?.source_agent;
      if (sourceAgent) {
        updateAgentActivity(sourceAgent);
      }
    };

    // Subscribe to all event types
    const unsubscribers = [
      websocketService.subscribe('vip_update', handleMessage),
      websocketService.subscribe('escort_update', handleMessage),
      websocketService.subscribe('buggy_update', handleMessage),
      websocketService.subscribe('lounge_update', handleMessage),
      websocketService.subscribe('flight_update', handleMessage),
      websocketService.subscribe('baggage_update', handleMessage),
    ];

    return () => {
      unsubscribers.forEach(unsub => unsub());
    };
  }, []);

  const updateAgentActivity = (agentName: string) => {
    setAgents(prev => prev.map(agent => {
      // Match agent name (handle variations like "escort_agent" vs "escort")
      const matches = agentName.toLowerCase().includes(agent.name.toLowerCase()) ||
                     agent.name.toLowerCase().includes(agentName.toLowerCase());
      
      if (matches) {
        return {
          ...agent,
          status: 'active',
          lastActivity: new Date().toISOString(),
          activityCount: agent.activityCount + 1,
        };
      }
      return agent;
    }));

    // Reset to idle after 3 seconds
    setTimeout(() => {
      setAgents(prev => prev.map(agent => {
        const matches = agentName.toLowerCase().includes(agent.name.toLowerCase()) ||
                       agent.name.toLowerCase().includes(agentName.toLowerCase());
        
        if (matches && agent.status === 'active') {
          return { ...agent, status: 'idle' };
        }
        return agent;
      }));
    }, 3000);
  };

  const formatLastActivity = (isoString: string | null): string => {
    if (!isoString) return 'Never';
    
    const now = new Date();
    const then = new Date(isoString);
    const diffMs = now.getTime() - then.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    
    if (diffSec < 5) return 'Just now';
    if (diffSec < 60) return `${diffSec}s ago`;
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    return `${Math.floor(diffSec / 3600)}h ago`;
  };

  const totalActivity = agents.reduce((sum, agent) => sum + agent.activityCount, 0);
  const activeAgents = agents.filter(a => a.status === 'active').length;

  return (
    <div className="bg-control-panel border border-control-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-control-border bg-control-bg">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-control-text">Agent Status Monitor</h3>
            <p className="text-xs text-control-text-dim mt-1">
              Real-time agent activity tracking
            </p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold font-mono text-status-active">
              {activeAgents}/{agents.length}
            </div>
            <div className="text-xs text-control-text-dim">Active Agents</div>
          </div>
        </div>
      </div>

      {/* Agent Grid */}
      <div className="p-4 grid grid-cols-2 gap-3">
        {agents.map((agent) => (
          <div
            key={agent.name}
            className="bg-control-bg border border-control-border rounded-lg p-3 hover:border-control-border/80 transition-all"
          >
            <div className="flex items-start justify-between mb-2">
              {/* Agent Info */}
              <div className="flex items-center gap-2">
                <span className="text-2xl">{agent.icon}</span>
                <div>
                  <h4 className="text-sm font-bold text-control-text">
                    {agent.displayName}
                  </h4>
                  <p className="text-xs text-control-text-dim">
                    {agent.activityCount} events
                  </p>
                </div>
              </div>

              {/* Status Indicator */}
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${getStatusBg(agent.status)} ${
                  agent.status === 'active' ? 'animate-pulse' : ''
                }`} />
              </div>
            </div>

            {/* Status Badge */}
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-control-border">
              <span className={`text-xs font-mono font-semibold ${getStatusColor(agent.status)}`}>
                {getStatusLabel(agent.status)}
              </span>
              <span className="text-xs text-control-text-dim">
                {formatLastActivity(agent.lastActivity)}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Footer Stats */}
      <div className="p-3 border-t border-control-border bg-control-bg">
        <div className="flex items-center justify-between text-xs">
          <span className="text-control-text-dim">
            Total Events: <span className="text-control-text font-mono font-bold">{totalActivity}</span>
          </span>
          <span className="text-control-text-dim">
            System: <span className="text-status-active font-mono font-bold">OPERATIONAL</span>
          </span>
        </div>
      </div>
    </div>
  );
};
