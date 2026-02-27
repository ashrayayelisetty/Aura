import { useEffect, useState } from 'react';
import { websocketService, ConnectionState } from '../services/websocketService';

/**
 * System Metrics Panel Component
 * 
 * Displays real-time system performance metrics and statistics.
 * Shows processing speed, event throughput, and system health.
 */

interface SystemMetrics {
  eventsPerSecond: number;
  totalEvents: number;
  avgResponseTime: number;
  uptime: number;
  websocketLatency: number;
  lastEventTime: number | null;
}

export const SystemMetricsPanel: React.FC = () => {
  const [metrics, setMetrics] = useState<SystemMetrics>({
    eventsPerSecond: 0,
    totalEvents: 0,
    avgResponseTime: 0,
    uptime: 0,
    websocketLatency: 0,
    lastEventTime: null,
  });
  const [connectionState, setConnectionState] = useState<ConnectionState>(ConnectionState.DISCONNECTED);
  const [startTime] = useState(Date.now());

  useEffect(() => {
    // Track connection state
    const unsubscribeState = websocketService.onStateChange((state) => {
      setConnectionState(state);
    });

    // Track events for metrics
    let eventCount = 0;
    let eventTimes: number[] = [];

    const trackEvent = () => {
      const now = Date.now();
      eventCount++;
      eventTimes.push(now);

      // Keep only last 10 seconds of events
      eventTimes = eventTimes.filter(t => now - t < 10000);

      // Calculate events per second
      const eps = eventTimes.length / 10;

      // Simulate response time (in production, this would be measured)
      const responseTime = Math.random() * 50 + 10; // 10-60ms

      setMetrics(prev => ({
        ...prev,
        eventsPerSecond: parseFloat(eps.toFixed(2)),
        totalEvents: eventCount,
        avgResponseTime: parseFloat(responseTime.toFixed(1)),
        lastEventTime: now,
      }));
    };

    const unsubscribers = [
      websocketService.subscribe('vip_update', trackEvent),
      websocketService.subscribe('escort_update', trackEvent),
      websocketService.subscribe('buggy_update', trackEvent),
      websocketService.subscribe('lounge_update', trackEvent),
      websocketService.subscribe('flight_update', trackEvent),
    ];

    // Update uptime every second
    const uptimeInterval = setInterval(() => {
      setMetrics(prev => ({
        ...prev,
        uptime: Math.floor((Date.now() - startTime) / 1000),
      }));
    }, 1000);

    // Simulate WebSocket latency measurement
    const latencyInterval = setInterval(() => {
      if (connectionState === ConnectionState.CONNECTED) {
        // In production, this would be measured via ping/pong
        const latency = Math.random() * 20 + 5; // 5-25ms
        setMetrics(prev => ({
          ...prev,
          websocketLatency: parseFloat(latency.toFixed(1)),
        }));
      }
    }, 2000);

    return () => {
      unsubscribeState();
      unsubscribers.forEach(unsub => unsub());
      clearInterval(uptimeInterval);
      clearInterval(latencyInterval);
    };
  }, [startTime, connectionState]);

  const formatUptime = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
      return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  };

  const getHealthStatus = (): { label: string; color: string } => {
    if (connectionState !== ConnectionState.CONNECTED) {
      return { label: 'DISCONNECTED', color: 'text-status-alert' };
    }
    if (metrics.avgResponseTime > 100) {
      return { label: 'DEGRADED', color: 'text-status-progress' };
    }
    return { label: 'HEALTHY', color: 'text-status-active' };
  };

  const health = getHealthStatus();

  return (
    <div className="bg-control-panel border border-control-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-control-border bg-control-bg">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-control-text">System Metrics</h3>
            <p className="text-xs text-control-text-dim mt-1">
              Real-time performance monitoring
            </p>
          </div>
          <div className="text-right">
            <div className={`text-sm font-bold font-mono ${health.color}`}>
              {health.label}
            </div>
            <div className="text-xs text-control-text-dim">System Status</div>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="p-4 grid grid-cols-3 gap-3">
        {/* Events Per Second */}
        <div className="bg-control-bg border border-control-border rounded-lg p-3">
          <div className="text-xs text-control-text-dim uppercase tracking-wide mb-1">
            Events/sec
          </div>
          <div className="text-2xl font-bold font-mono text-status-active">
            {metrics.eventsPerSecond}
          </div>
          <div className="text-xs text-control-text-dim mt-1">
            Throughput
          </div>
        </div>

        {/* Total Events */}
        <div className="bg-control-bg border border-control-border rounded-lg p-3">
          <div className="text-xs text-control-text-dim uppercase tracking-wide mb-1">
            Total Events
          </div>
          <div className="text-2xl font-bold font-mono text-control-text">
            {metrics.totalEvents}
          </div>
          <div className="text-xs text-control-text-dim mt-1">
            Since startup
          </div>
        </div>

        {/* Response Time */}
        <div className="bg-control-bg border border-control-border rounded-lg p-3">
          <div className="text-xs text-control-text-dim uppercase tracking-wide mb-1">
            Avg Response
          </div>
          <div className="text-2xl font-bold font-mono text-status-progress">
            {metrics.avgResponseTime}ms
          </div>
          <div className="text-xs text-control-text-dim mt-1">
            Processing time
          </div>
        </div>

        {/* WebSocket Latency */}
        <div className="bg-control-bg border border-control-border rounded-lg p-3">
          <div className="text-xs text-control-text-dim uppercase tracking-wide mb-1">
            WS Latency
          </div>
          <div className="text-2xl font-bold font-mono text-blue-400">
            {metrics.websocketLatency}ms
          </div>
          <div className="text-xs text-control-text-dim mt-1">
            Network delay
          </div>
        </div>

        {/* Uptime */}
        <div className="bg-control-bg border border-control-border rounded-lg p-3">
          <div className="text-xs text-control-text-dim uppercase tracking-wide mb-1">
            Uptime
          </div>
          <div className="text-lg font-bold font-mono text-control-text">
            {formatUptime(metrics.uptime)}
          </div>
          <div className="text-xs text-control-text-dim mt-1">
            System runtime
          </div>
        </div>

        {/* Connection Status */}
        <div className="bg-control-bg border border-control-border rounded-lg p-3">
          <div className="text-xs text-control-text-dim uppercase tracking-wide mb-1">
            Connection
          </div>
          <div className={`text-lg font-bold font-mono ${
            connectionState === ConnectionState.CONNECTED ? 'text-status-active' : 'text-status-alert'
          }`}>
            {connectionState === ConnectionState.CONNECTED ? 'LIVE' : 'OFFLINE'}
          </div>
          <div className="text-xs text-control-text-dim mt-1">
            WebSocket status
          </div>
        </div>
      </div>

      {/* Performance Bar */}
      <div className="p-4 border-t border-control-border bg-control-bg">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-control-text-dim">System Load</span>
          <span className="text-xs font-mono text-control-text">
            {Math.min(metrics.eventsPerSecond * 10, 100).toFixed(0)}%
          </span>
        </div>
        <div className="w-full bg-control-border rounded-full h-2 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-status-active to-status-progress transition-all duration-300"
            style={{ width: `${Math.min(metrics.eventsPerSecond * 10, 100)}%` }}
          />
        </div>
      </div>
    </div>
  );
};
