import { useState, useCallback } from 'react';
import type { CaseState } from '../types/case';
import { CaseStatus } from '../types/case';
import type { AgentThought, EventLogEntry, ProgressUpdate } from '../types/websocket';

const initialState: CaseState = {
  status: CaseStatus.IDLE,
  progress: 0,
  stage: 'Waiting',
  agents: [
    { id: 'coordinator', name: 'Coordinator Alpha', state: 'idle', confidence: 0 },
    { id: 'context_weaver', name: 'Context Weaver', state: 'idle', confidence: 0 },
    { id: 'echo_vault', name: 'Echo Vault', state: 'idle', confidence: 0 },
    { id: 'outcome_architect', name: 'Outcome Architect', state: 'idle', confidence: 0 },
    { id: 'chronicle_scribe', name: 'Chronicle Scribe', state: 'idle', confidence: 0 },
    { id: 'pulse_monitor', name: 'Pulse Monitor', state: 'idle', confidence: 0 }
  ],
  connections: [],
  eventLog: []
};

export function useCaseState() {
  const [caseState, setCaseState] = useState<CaseState>(initialState);

  const updateProgress = useCallback((update: ProgressUpdate) => {
    setCaseState(prev => ({
      ...prev,
      progress: update.percent,
      stage: update.stage,
      status: update.percent === 100 ? CaseStatus.COMPLETE : CaseStatus.ANALYZING
    }));
  }, []);

  const addAgentThought = useCallback((thought: AgentThought) => {
    setCaseState(prev => {
      const updatedAgents = prev.agents.map(a => 
        a.id === thought.agentId 
          ? { ...a, state: thought.state, confidence: thought.confidence, lastThought: thought.query }
          : a
      );
      
      return {
        ...prev,
        agents: updatedAgents,
        currentAgent: thought.agentId
      };
    });
  }, []);

  const addEventLog = useCallback((entry: EventLogEntry | string, agent?: string, message?: string) => {
    if (typeof entry === 'string') {
      const newEntry: EventLogEntry = {
        id: Date.now().toString(),
        timestamp: Date.now(),
        level: entry as any,
        agent: agent || 'System',
        message: message || ''
      };
      setCaseState(prev => ({
        ...prev,
        eventLog: [...prev.eventLog, newEntry]
      }));
    } else {
      setCaseState(prev => ({
        ...prev,
        eventLog: [...prev.eventLog, entry]
      }));
    }
  }, []);

  const setDeliverables = useCallback((deliverables: any) => {
    setCaseState(prev => ({
      ...prev,
      status: CaseStatus.COMPLETE,
      deliverables
    }));
  }, []);

  const resetCase = useCallback(() => {
    setCaseState(initialState);
  }, []);

  return {
    caseState,
    updateProgress,
    addAgentThought,
    addEventLog,
    setDeliverables,
    resetCase
  };
}
