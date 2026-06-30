import { useRef, useEffect } from 'react';
import { 
  Info, 
  AlertTriangle, 
  CheckCircle, 
  Brain, 
  MessageSquare,
  Zap
} from 'lucide-react';
import { CaseStatus } from '../../types/case';
import type { EventLogEntry } from '../../types/websocket';

interface EventLogProps {
  entries: EventLogEntry[];
  status: CaseStatus;
  progress: number;
  stage: string;
}

const levelConfig: Record<string, { icon: any; color: string }> = {
  INFO: { icon: Info, color: '#111' },
  THINK: { icon: Brain, color: '#111' },
  DEBATE: { icon: MessageSquare, color: '#111' },
  SUCCESS: { icon: CheckCircle, color: '#111' },
  WARNING: { icon: AlertTriangle, color: '#111' },
  ERROR: { icon: AlertTriangle, color: '#111' }
};

export function EventLog({ entries, status, progress, stage }: EventLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries]);

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit'
    });
  };

  return (
    <div className="flex flex-col h-full overflow-hidden text-[#111] dark:text-[#eee]">
      <div className="flex items-center justify-between p-4 border-b-4 border-[#111] dark:border-[#eee] bg-[#f4f4f0] dark:bg-[#111]">
        <div className="flex items-center space-x-2">
          <Zap size={16} />
          <span className="text-sm font-black uppercase tracking-wider">{stage}</span>
        </div>
        <div className="flex items-center space-x-3 w-1/2">
          <div className="flex-1 h-3 border-2 border-[#111] dark:border-[#eee] bg-white dark:bg-[#0a0a0a] overflow-hidden">
            <div 
              className="h-full bg-[#111] dark:bg-[#eee] transition-all duration-500" 
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-xs font-mono font-bold">{Math.round(progress)}%</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4" ref={scrollRef}>
        {entries.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-800 dark:text-gray-400">
            <p className="font-bold uppercase">Waiting for files...</p>
            <span className="text-xs mt-2 font-mono">Drop documents to activate the swarm</span>
          </div>
        ) : (
          entries.map((entry) => {
            const config = levelConfig[entry.level];
            const Icon = config.icon;
            
            return (
              <div key={entry.id} className="flex space-x-3 text-sm border-b-2 border-dashed border-gray-300 dark:border-gray-700 pb-4 last:border-0">
                <div className="text-[10px] font-mono text-gray-800 dark:text-gray-400 pt-1 w-16 shrink-0">
                  {formatTime(entry.timestamp)}
                </div>
                <div className="pt-0.5">
                  <Icon size={14} />
                </div>
                <div className="flex-1 space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="font-black uppercase">
                      {entry.agent}
                    </span>
                    <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 border border-[#111] dark:border-[#eee]">
                      {entry.level}
                    </span>
                  </div>
                  <p className="font-mono text-xs leading-relaxed">{entry.message}</p>
                  {entry.metadata && Object.keys(entry.metadata).length > 0 && (
                    <details className="mt-2 text-xs">
                      <summary className="cursor-pointer font-bold hover:underline">Details</summary>
                      <pre className="mt-2 p-2 bg-[#f4f4f0] dark:bg-[#111] border-2 border-[#111] dark:border-[#eee] overflow-x-auto font-mono">
                        {JSON.stringify(entry.metadata, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            );
          })
        )}
        
        {status !== CaseStatus.COMPLETE && status !== CaseStatus.IDLE && (
          <div className="flex items-center space-x-2 text-xs font-bold uppercase pt-4">
            <span className="w-2 h-2 rounded-full bg-[#111] dark:bg-[#eee] animate-pulse" />
            <span>Live processing...</span>
          </div>
        )}
      </div>
    </div>
  );
}
