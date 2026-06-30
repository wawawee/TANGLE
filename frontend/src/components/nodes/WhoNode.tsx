import { Handle, Position } from '@xyflow/react';
import { useState } from 'react';
import { ArrowRight } from 'lucide-react';

export function WhoNode({ data, id }: any) {
  const [value, setValue] = useState('');

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && value.trim()) {
      data.onSubmit(id, value.trim());
    }
  };

  return (
    <div className="brutalist-card p-8 w-[40rem] flex flex-col space-y-6">
      <label className="text-5xl font-black uppercase tracking-tighter">Objective</label>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="e.g. Help Anders return his broken playstation"
        className="border-b-4 border-[#111] pb-2 outline-none text-xl font-mono placeholder-gray-400 bg-transparent w-full"
        autoFocus
        disabled={data.submitted}
      />
      {!data.submitted && (
        <button 
          onClick={() => value.trim() && data.onSubmit(id, value.trim())}
          className="brutalist-button self-end p-3 flex items-center justify-center"
        >
          <ArrowRight size={24} strokeWidth={3} />
        </button>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
