export type EventType = 'status' | 'output' | 'metric' | 'info' | 'workflow_status' | 'snapshot' | 'prompt' | 'error';

export interface TelemetryEvent {
  timestamp: string;
  session_id: string;
  node: string;
  event_type: EventType;
  source: 'system' | 'llm';
  data: any;
}

export type NodeStatus = 'active' | 'success' | 'failed' | 'idle' | 'error' | 'approved' | 'rejected' | 'pending' | 'journaled';

export interface NodeState {
  id: string;
  status: NodeStatus;
  lastUpdated: string;
  logs: TelemetryEvent[];
  timer?: number;
}
