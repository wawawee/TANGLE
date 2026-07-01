import { useState } from 'react';
import { ChevronRight, Brain, ArrowRight } from 'lucide-react';

interface SolutionPath {
  id: string;
  title: string;
  summary: string;
  confidence: number;
  pros: string[];
  cons: string[];
}

interface DecisionPointProps {
  title: string;
  description: string;
  options: SolutionPath[];
  onSelect: (optionId: string) => void;
  onDismiss?: () => void;
}

export function DecisionPoint({ title, description, options, onSelect, onDismiss }: DecisionPointProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-[700px] max-w-[90vw] max-h-[85vh] overflow-y-auto border-2 border-[#00d4ff] bg-[#0a0a0a] shadow-[0_0_40px_rgba(0,212,255,0.15)]">
        {/* Header */}
        <div className="border-b border-[#222] p-5">
          <div className="flex items-center gap-2 mb-2">
            <Brain size={18} className="text-[#00d4ff]" />
            <h2 className="text-sm font-black uppercase tracking-wider text-[#00d4ff]">{title}</h2>
          </div>
          <p className="text-xs text-gray-400 leading-relaxed">{description}</p>
        </div>

        {/* Options */}
        <div className="p-4 space-y-3">
          {options.map((opt) => (
            <div
              key={opt.id}
              className={`border p-4 cursor-pointer transition-all ${
                selected === opt.id
                  ? 'border-[#00d4ff] bg-[#00d4ff]08'
                  : 'border-[#222] hover:border-[#444] bg-black/50'
              }`}
              onClick={() => setSelected(opt.id)}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                      selected === opt.id ? 'border-[#00d4ff]' : 'border-gray-600'
                    }`}>
                      {selected === opt.id && <div className="w-2 h-2 rounded-full bg-[#00d4ff]" />}
                    </div>
                    <h3 className="text-sm font-bold text-gray-200">{opt.title}</h3>
                  </div>
                  <p className="text-xs text-gray-500 mt-2 ml-6">{opt.summary}</p>
                </div>
                <div className="text-right shrink-0 ml-4">
                  <div className="text-[10px] text-gray-600 uppercase">Confidence</div>
                  <div className="text-sm font-bold" style={{ color: opt.confidence > 0.7 ? '#00ff88' : opt.confidence > 0.4 ? '#f59e0b' : '#ef4444' }}>
                    {Math.round(opt.confidence * 100)}%
                  </div>
                </div>
              </div>

              {/* Expand for pros/cons */}
              <div className="ml-6 mt-2">
                <button
                  onClick={(e) => { e.stopPropagation(); setExpanded(expanded === opt.id ? null : opt.id); }}
                  className="text-[10px] text-[#00d4ff] font-bold uppercase flex items-center gap-1 hover:underline"
                >
                  <ChevronRight size={12} className={`transition-transform ${expanded === opt.id ? 'rotate-90' : ''}`} />
                  {expanded === opt.id ? 'Hide Details' : 'Show Details'}
                </button>

                {expanded === opt.id && (
                  <div className="mt-2 grid grid-cols-2 gap-4">
                    <div>
                      <span className="text-[10px] text-green-500 font-bold uppercase">Pros</span>
                      <ul className="mt-1 space-y-1">
                        {opt.pros.map((pro, i) => (
                          <li key={i} className="text-[10px] text-gray-400 flex items-start gap-1">
                            <span className="text-green-500 mt-0.5">+</span> {pro}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <span className="text-[10px] text-red-400 font-bold uppercase">Cons</span>
                      <ul className="mt-1 space-y-1">
                        {opt.cons.map((con, i) => (
                          <li key={i} className="text-[10px] text-gray-400 flex items-start gap-1">
                            <span className="text-red-400 mt-0.5">-</span> {con}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Actions */}
        <div className="border-t border-[#222] p-4 flex justify-between items-center">
          {onDismiss && (
            <button onClick={onDismiss} className="text-xs text-gray-500 hover:text-gray-300 uppercase font-bold">
              Skip — use best path
            </button>
          )}
          <button
            onClick={() => selected && onSelect(selected)}
            disabled={!selected}
            className="ml-auto flex items-center gap-2 px-5 py-2 bg-[#00d4ff] text-black font-bold uppercase text-xs rounded hover:bg-[#00d4ff]/80 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            Continue <ArrowRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
