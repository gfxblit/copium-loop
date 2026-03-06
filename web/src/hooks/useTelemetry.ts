import { useState, useEffect, useCallback, useRef } from 'react';
import type { TelemetryEvent, NodeState, NodeStatus } from '../types';

export function useTelemetry() {
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [nodeStates, setNodeStates] = useState<Record<string, NodeState>>({});
  const [workflowStatus, setWorkflowStatus] = useState<string>('idle');
  const [connected, setConnected] = useState(false);
  const ws = useRef<WebSocket | null>(null);

  const processEvent = useCallback((event: TelemetryEvent) => {
    if (event.event_type === 'snapshot') {
      const snapshotEvents = event.data as TelemetryEvent[];
      setEvents(snapshotEvents);
      
      const states: Record<string, NodeState> = {};
      snapshotEvents.forEach(e => {
        if (e.event_type === 'status') {
          states[e.node] = {
            id: e.node,
            status: e.data as NodeStatus,
            lastUpdated: e.timestamp,
            logs: []
          };
        }
      });
      
      // Associate logs
      snapshotEvents.forEach(e => {
        if (states[e.node]) {
          states[e.node].logs.push(e);
        }
      });
      
      setNodeStates(states);
      return;
    }

    setEvents(prev => [...prev, event]);

    if (event.event_type === 'status') {
      setNodeStates(prev => ({
        ...prev,
        [event.node]: {
          ...(prev[event.node] || { id: event.node, logs: [] }),
          status: event.data as NodeStatus,
          lastUpdated: event.timestamp,
        }
      }));
    }

    if (event.event_type === 'workflow_status') {
      setWorkflowStatus(event.data as string);
    }

    // Add event to node logs
    if (event.node && event.node !== 'workflow') {
      setNodeStates(prev => {
        const nodeState = prev[event.node] || { id: event.node, status: 'pending', lastUpdated: event.timestamp, logs: [] };
        return {
          ...prev,
          [event.node]: {
            ...nodeState,
            logs: [...nodeState.logs, event]
          }
        };
      });
    }
  }, []);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    // For development when running vite dev server on 5173 and backend on 8000
    const wsUrl = host.includes('5173') 
      ? `${protocol}//${window.location.hostname}:8000/api/ws`
      : `${protocol}//${host}/api/ws`;

    console.log('Connecting to WebSocket:', wsUrl);
    const socket = new WebSocket(wsUrl);
    ws.current = socket;

    socket.onopen = () => {
      console.log('WebSocket connected');
      setConnected(true);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        processEvent(data);
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    };

    socket.onclose = () => {
      console.log('WebSocket disconnected');
      setConnected(false);
      // Try to reconnect after 3 seconds
      setTimeout(() => {
        if (ws.current === socket) {
           // trigger effect again by some state change if needed, 
           // but for now simple reconnect
        }
      }, 3000);
    };

    return () => {
      socket.close();
    };
  }, [processEvent]);

  return { events, nodeStates, workflowStatus, connected };
}
