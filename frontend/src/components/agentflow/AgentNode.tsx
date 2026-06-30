import { Handle, Position } from '@xyflow/react';

export function AgentNode({ data }: any) {
  const isActive = data.isActive;
  const stateColor = 
    data.state === 'idle' ? '#ccc' :
    data.state === 'querying' ? '#00d4ff' :
    data.state === 'reasoning' ? '#a855f7' :
    data.state === 'debating' ? '#f59e0b' :
    '#00ff88';

  return (
    <div className={`brutalist-card p-4 min-w-[200px] border-l-8 transition-all ${isActive ? 'scale-105' : ''}`} style={{ borderLeftColor: stateColor }}>
      <Handle type="target" position={Position.Top} />
      
      <div className="flex flex-col space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-black uppercase tracking-wider text-gray-800 dark:text-gray-400">{data.role}</span>
          <div className="flex items-center space-x-1 border-2 border-[#111] dark:border-[#eee] px-1 bg-[#f4f4f0] dark:bg-[#111]">
            <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: stateColor }} />
            <span className="text-[10px] font-bold uppercase dark:text-[#eee]">{data.state}</span>
          </div>
        </div>
        
        <h3 className="text-sm font-black uppercase dark:text-[#eee]">{data.name}</h3>
        
        {data.confidence > 0 && (
          <div className="w-full border-2 border-[#111] dark:border-[#eee] h-2 bg-[#f4f4f0] dark:bg-[#111] mt-2">
            <div 
              className="h-full bg-[#111] dark:bg-[#eee] transition-all duration-500" 
              style={{ width: `${data.confidence * 100}%` }}
            />
          </div>
        )}
        
        {data.lastThought && (
          <div className="mt-2 text-xs font-mono border-t-2 border-[#111] dark:border-[#eee] pt-2 dark:text-[#eee]">
            "{data.lastThought}"
          </div>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
