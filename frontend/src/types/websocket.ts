export interface ProgressUpdate {
  stage: string;
  percent: number;
  message: string;
  etaSeconds?: number;
}

export interface AgentThought {
  agentId: string;
  state: string;
  query?: string;
  evidence: string[];
  conclusion?: string;
  confidence: number;
  timestamp: number;
}

export interface EventLogEntry {
  id: string;
  timestamp: number;
  level: 'INFO' | 'THINK' | 'DEBATE' | 'SUCCESS' | 'WARNING' | 'ERROR';
  agent: string;
  message: string;
  metadata?: Record<string, unknown>;
}
