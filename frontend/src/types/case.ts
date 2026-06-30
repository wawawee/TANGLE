export const CaseStatus = {
  IDLE: 'IDLE',
  CREATED: 'CREATED',
  UPLOADING: 'UPLOADING',
  ANALYZING: 'ANALYZING',
  DEBATING: 'DEBATING',
  SYNTHESIZING: 'SYNTHESIZING',
  COMPLETE: 'COMPLETE',
  FAILED: 'FAILED'
} as const;

export type CaseStatus = (typeof CaseStatus)[keyof typeof CaseStatus];

export interface CaseState {
  status: CaseStatus;
  progress: number;
  stage: string;
  agents: any[];
  connections: any[];
  currentAgent?: string;
  eventLog: any[];
  deliverables?: any;
}
