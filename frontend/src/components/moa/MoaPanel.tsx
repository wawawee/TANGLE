import { useState, useRef, useEffect } from 'react';
import { Zap, Loader2, ChevronDown, ChevronRight, Check, X, AlertTriangle } from 'lucide-react';

interface RefOutput {
  model: string;
  output: string;
  status: 'running' | 'done' | 'error';
  error?: string;
}

interface MoaPanelProps {
  evidenceTexts: { source: string; text: string }[];
  entityName?: string;
}

export function MoaPanel({ evidenceTexts, entityName }: MoaPanelProps) {
  const [phase, setPhase] = useState<'idle' | 'reference' | 'aggregator' | 'complete' | 'error'>('idle');
  const [refOutputs, setRefOutputs] = useState<RefOutput[]>([]);
  const [finalAnswer, setFinalAnswer] = useState('');
  const [error, setError] = useState('');
  const [expandedRef, setExpandedRef] = useState<number | null>(null);
  const [modelsUsed, setModelsUsed] = useState<string[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const canRun = evidenceTexts.length > 0 && phase === 'idle';

  const buildPrompt = () => {
    const context = evidenceTexts.map(e =>
      `--- ${e.source} ---\n${e.text.slice(0, 3000)}`
    ).join('\n\n');
    return `Analyze the following evidence for ${entityName || 'this case'}:\n\n${context}\n\nProvide a comprehensive analysis covering: key findings, critical information, risks, and recommended actions.`;
  };

  const runDeepAnalysis = async () => {
    setPhase('reference');
    setError('');
    setFinalAnswer('');
    setModelsUsed([]);
    setRefOutputs([
      { model: 'llama-3.2-3b-instruct', output: '', status: 'running' },
      { model: 'gemma-2-2b-it', output: '', status: 'running' },
      { model: 'phi-3-mini-128k-instruct', output: '', status: 'running' },
    ]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const resp = await fetch('/api/moa/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: buildPrompt(),
          system_prompt: 'You are a legal analyst assistant.',
          entity: entityName || '',
        }),
        signal: controller.signal,
      });

      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`Server error (${resp.status}): ${text.slice(0, 200)}`);
      }

      const reader = resp.body?.getReader();
      if (!reader) throw new Error('No response stream');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            const eventType = line.slice(7).trim();
            continue;
          }
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));

            switch (data.phase || eventType) {
              case 'phase':
                // Handled via event type
                break;

              case 'ref_done': {
                const modelName = data.model.split(':')[0] || data.model;
                setRefOutputs(prev => prev.map(r =>
                  r.model === modelName || modelName.includes(r.model.split('-')[0])
                    ? { ...r, output: data.output, status: 'done' }
                    : r
                ));
                break;
              }

              case 'ref_error': {
                const modelName = data.model.split(':')[0] || data.model;
                setRefOutputs(prev => prev.map(r =>
                  r.model === modelName || modelName.includes(r.model.split('-')[0])
                    ? { ...r, status: 'error', error: data.error }
                    : r
                ));
                break;
              }

              case 'complete':
                setFinalAnswer(data.final || '');
                setModelsUsed(data.models_used || []);
                setPhase('complete');
                break;
            }
          }
        }

        // Detect phase change from event data
        if (buffer.includes('event: phase')) {
          const match = buffer.match(/event: phase\ndata: ({.+})/);
          if (match) {
            const phaseData = JSON.parse(match[1]);
            if (phaseData.phase === 'aggregator') {
              setPhase('aggregator');
              buffer = buffer.replace(/event: phase\ndata: {.+}\n\n?/, '');
            }
          }
        }
      }

      if (phase !== 'complete') {
        setPhase('complete');
      }
    } catch (err: any) {
      if (err.name === 'AbortError') return;
      setError(err.message || 'Analysis failed');
      setPhase('error');
    }
  };

  const modelLabel = (name: string) => {
    const short = name.split('/').pop() || name;
    return short.replace(/:free$/, '').replace(/-instruct$/, '').replace(/-/g, ' ');
  };

  return (
    <div className="flex flex-col h-full p-3 text-[#111] dark:text-[#eee] font-mono text-xs">
      {/* Header */}
      <div className="flex items-center justify-between border-b-2 border-[#111] dark:border-[#eee] pb-2 mb-3">
        <div className="flex items-center space-x-2">
          <Zap size={14} />
          <span className="font-bold uppercase text-sm">Deep Analysis</span>
        </div>
        {phase !== 'idle' && (
          <span className="text-[10px] opacity-60 uppercase">
            {phase === 'reference' && 'Running reference models...'}
            {phase === 'aggregator' && 'Synthesizing...'}
            {phase === 'complete' && 'Complete'}
            {phase === 'error' && 'Failed'}
          </span>
        )}
      </div>

      {/* Init state */}
      {phase === 'idle' && (
        <div className="flex flex-col items-center justify-center flex-1 space-y-3 text-center">
          <Zap size={32} className="opacity-30" />
          <p className="text-xs opacity-60 max-w-xs">
            Runs 3 independent models in parallel, then synthesizes their analyses into one answer.
          </p>
          {!canRun && (
            <p className="text-[10px] text-[#ff003c]">Upload evidence first</p>
          )}
          <button
            onClick={runDeepAnalysis}
            disabled={!canRun}
            className="brutalist-button py-2 px-6 flex items-center space-x-2 bg-[#00ff88] text-[#111] border-[#111] hover:bg-[#111] hover:text-[#00ff88] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Zap size={14} />
            <span>Run Deep Analysis</span>
          </button>
        </div>
      )}

      {/* Running state */}
      {(phase === 'reference' || phase === 'aggregator') && (
        <div className="flex flex-col flex-1 space-y-3">
          {/* Reference model progress */}
          <div className="space-y-1.5">
            <p className="font-bold text-[10px] uppercase opacity-60">Reference Models</p>
            {refOutputs.map((ref, i) => (
              <div key={i} className="border border-[#111] dark:border-[#eee] p-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    {ref.status === 'running' && <Loader2 size={12} className="animate-spin" />}
                    {ref.status === 'done' && <Check size={12} className="text-[#00cc66]" />}
                    {ref.status === 'error' && <X size={12} className="text-[#ff003c]" />}
                    <span className="font-mono text-[10px] uppercase">{modelLabel(ref.model)}</span>
                  </div>
                  {ref.status !== 'running' && (
                    <button
                      onClick={() => setExpandedRef(expandedRef === i ? null : i)}
                      className="hover:opacity-60"
                    >
                      {expandedRef === i ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                    </button>
                  )}
                </div>
                {expandedRef === i && ref.output && (
                  <div className="mt-1.5 p-1.5 bg-[#f4f4f0] dark:bg-[#1a1a1a] text-[10px] max-h-24 overflow-y-auto whitespace-pre-wrap leading-tight">
                    {ref.output.slice(0, 2000)}
                  </div>
                )}
                {expandedRef === i && ref.error && (
                  <div className="mt-1.5 p-1.5 bg-red-50 dark:bg-red-900/20 text-[#ff003c] text-[10px] leading-tight">
                    {ref.error}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Phase indicator */}
          {phase === 'aggregator' && (
            <div className="border-2 border-[#111] dark:border-[#eee] bg-[#111] text-[#00ff88] dark:bg-black dark:text-[#00ff88] p-2 text-[10px] flex items-center space-x-2">
              <Loader2 size={12} className="animate-spin shrink-0" />
              <span>Synthesizing with Hermes 3 70B...</span>
            </div>
          )}
        </div>
      )}

      {/* Complete state */}
      {phase === 'complete' && (
        <div className="flex flex-col flex-1 space-y-3 overflow-hidden">
          {/* Models used */}
          <div className="flex flex-wrap gap-1">
            {modelsUsed.map((m, i) => (
              <span
                key={i}
                className={`text-[9px] px-1.5 py-0.5 border border-[#111] dark:border-[#eee] ${
                  i === modelsUsed.length - 1
                    ? 'bg-[#111] text-white dark:bg-[#eee] dark:text-[#111] font-bold'
                    : 'bg-transparent'
                }`}
              >
                {modelLabel(m)}
              </span>
            ))}
          </div>

          {/* Reference outputs (collapsible) */}
          <div>
            <button
              onClick={() => setExpandedRef(expandedRef === -1 ? null : -1)}
              className="flex items-center space-x-1 text-[10px] uppercase opacity-60 hover:opacity-100"
            >
              {expandedRef === -1 ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              <span>Reference outputs ({refOutputs.filter(r => r.status === 'done').length}/3)</span>
            </button>
            {expandedRef === -1 && (
              <div className="mt-1 space-y-1 max-h-20 overflow-y-auto">
                {refOutputs.filter(r => r.status === 'done').map((ref, i) => (
                  <div key={i} className="p-1 bg-[#f4f4f0] dark:bg-[#1a1a1a] text-[9px] leading-tight">
                    <span className="font-bold uppercase">{modelLabel(ref.model)}:</span>{' '}
                    {ref.output.slice(0, 300)}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Final answer */}
          <div className="flex-1 overflow-y-auto border border-[#111] dark:border-[#eee] p-2 bg-[#f4f4f0] dark:bg-[#1a1a1a]">
            <div className="font-bold text-[10px] uppercase mb-1">Synthesized Analysis</div>
            <div className="text-[10px] leading-relaxed whitespace-pre-wrap">
              {finalAnswer}
            </div>
          </div>

          {/* Re-run */}
          <button
            onClick={runDeepAnalysis}
            className="brutalist-button py-1.5 px-4 text-[10px] flex items-center justify-center space-x-1"
          >
            <Zap size={10} />
            <span>Run Again</span>
          </button>
        </div>
      )}

      {/* Error state */}
      {phase === 'error' && (
        <div className="flex flex-col items-center justify-center flex-1 space-y-3 text-center">
          <AlertTriangle size={24} className="text-[#ff003c]" />
          <p className="text-[#ff003c] text-[10px]">{error || 'Analysis failed'}</p>
          <button
            onClick={runDeepAnalysis}
            className="brutalist-button py-1.5 px-4 text-[10px]"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
