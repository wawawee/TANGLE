const BACKEND_URL = 'http://localhost:8000';

export async function apiFetch(path: string, options?: RequestInit) {
  const url = `${BACKEND_URL}${path}`;
  const isFormData = options?.body instanceof FormData;
  const response = await fetch(url, {
    ...options,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new Error(`API Error: ${response.status} ${response.statusText}${text ? ` — ${text.slice(0, 200)}` : ''}`);
  }
  return response.json();
}

// ─── System ──────────────────────────────────────────

export async function getSystemHealth() {
  return apiFetch('/health');
}

export async function getProviderHealth() {
  return apiFetch('/api/health/providers');
}

export async function getUsageStats() {
  return apiFetch('/api/health/usage');
}

export async function getSystemMetrics() {
  return apiFetch('/api/system/metrics');
}

export async function getSystemProcesses() {
  return apiFetch('/api/system/processes');
}

export async function killProcess(pid: number, signal: string = 'SIGTERM') {
  return apiFetch('/api/system/kill', {
    method: 'POST',
    body: JSON.stringify({ pid, signal }),
  });
}

export async function executeTerminal(command: string, timeout: number = 30) {
  return apiFetch('/api/terminal/execute', {
    method: 'POST',
    body: JSON.stringify({ command, timeout }),
  });
}

// ─── Agents ──────────────────────────────────────────

export async function getAgentConfigs() {
  return apiFetch('/agents');
}

export async function saveAgentConfigs() {
  return { status: 'ok' };
}

export async function adminChat(message: string) {
  return apiFetch('/api/agents/execute', {
    method: 'POST',
    body: JSON.stringify({ agent_id: 'orchestrator', task: message }),
  });
}

export async function agentChat(agent: string, message: string) {
  return apiFetch('/api/agents/execute', {
    method: 'POST',
    body: JSON.stringify({ agent_id: agent, task: message }),
  });
}

export async function executeAgentWorkflow(tasks: { agent_id: string; task: string }[]) {
  return apiFetch('/api/agents/workflow', {
    method: 'POST',
    body: JSON.stringify({ tasks }),
  });
}

export async function stopAllAgents() {
  return apiFetch('/api/agents/stop', { method: 'POST' });
}

// ─── Upload ──────────────────────────────────────────

export async function uploadFile(file: File, entity: string = 'default') {
  const form = new FormData();
  form.append('file', file);
  form.append('entity', entity);
  return apiFetch('/api/upload', {
    method: 'POST',
    body: form,
  });
}

// ─── Missions ────────────────────────────────────────

export async function getEntities() {
  return apiFetch('/api/entities');
}

export async function getMissions(entity?: string) {
  const params = entity ? `?entity=${encodeURIComponent(entity)}` : '';
  return apiFetch(`/api/missions${params}`);
}

export async function startMission(objective: string, entity: string = 'default', files: string[] = []) {
  return apiFetch('/api/mission/start', {
    method: 'POST',
    body: JSON.stringify({ objective, entity, files }),
  });
}

export async function getMissionCost(missionId: string) {
  return apiFetch(`/api/missions/${missionId}/cost`);
}

// ─── Harness (Code Review) ───────────────────────────

export async function runHarness(code: string, filename?: string) {
  return apiFetch('/api/harness/run', {
    method: 'POST',
    body: JSON.stringify({ code, filename }),
  });
}

// ─── Knowledge ───────────────────────────────────────

export async function getKnowledgeDocs() {
  return apiFetch('/api/knowledge');
}

export async function addKnowledgeDoc(title: string, content: string) {
  return apiFetch('/api/knowledge', {
    method: 'POST',
    body: JSON.stringify({ agent_id: title, task: content }),
  });
}

// ─── Tasks & Kanban ──────────────────────────────────

export async function getTasks() {
  return apiFetch('/api/tasks');
}

export async function createTask(title: string, description?: string) {
  return apiFetch('/api/tasks', {
    method: 'POST',
    body: JSON.stringify({ title, description }),
  });
}

export async function getKanban() {
  return apiFetch('/api/kanban');
}

// ─── History ─────────────────────────────────────────

export async function getRunHistory() {
  return apiFetch('/api/history');
}

// ─── Admin ───────────────────────────────────────────

export async function getAdminIndex() {
  return apiFetch('/api/admin/index');
}

export async function exportWiki() {
  return apiFetch('/api/admin/export-wiki', { method: 'POST' });
}

export async function previewWikiExport() {
  return apiFetch('/api/admin/export-wiki/preview');
}

export async function getQdrantStats() {
  return apiFetch('/api/admin/index').then(d => d.qdrant);
}

export async function clearQdrantMemory() {
  return { success: true, message: 'Memory clear not available — use Google RAG 2.0' };
}

// ─── Swarm (TWISTED flow) ────────────────────────────

export async function getWittyResponse(query: string) {
  return apiFetch('/api/agent/witty', {
    method: 'POST',
    body: JSON.stringify({ agent_id: 'orchestrator', task: query }),
  });
}

// ─── Contradiction Analysis ─────────────────────────

export async function analyzeContradictions(
  evidenceTexts: { source: string; text: string }[],
  entity: string = ''
) {
  return apiFetch('/api/contradictions/analyze', {
    method: 'POST',
    body: JSON.stringify({ evidence_texts: evidenceTexts, entity }),
  });
}
