import { useState, useEffect, useRef } from 'react';
import {
  X, Clock, FileText, Search, Loader2, ChevronRight, RotateCcw,
  GripVertical, Minimize2, Maximize2,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { getMissions, getMission, startMission } from '../../services/api';

interface MissionMeta {
  mission_id: string;
  entity_name: string;
  status: string;
  timestamp: string;
}

interface MissionDetail extends MissionMeta {
  report: string;
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

const STATUS_COLORS: Record<string, string> = {
  completed: 'text-[#00ff88] border-[#00ff88]',
  running: 'text-[#00d4ff] border-[#00d4ff]',
  failed: 'text-[#ff003c] border-[#ff003c]',
};

export function HistoryPanel({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [missions, setMissions] = useState<MissionMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<MissionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);

  const [position, setPosition] = useState({ x: 750, y: 80 });
  const [size, setSize] = useState({ width: 720, height: 500 });
  const dragRef = useRef<{ startX: number; startY: number; startPosX: number; startPosY: number } | null>(null);

  useEffect(() => {
    getMissions()
      .then(data => { setMissions(data.missions ?? []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setDetailLoading(true);
    setDetail(null);
    getMission(selectedId)
      .then(d => { setDetail(d as MissionDetail); setDetailLoading(false); })
      .catch(() => { setDetailLoading(false); });
  }, [selectedId]);

  const filtered = missions.filter(m =>
    !search || m.entity_name.toLowerCase().includes(search.toLowerCase())
  );

  const selectedMeta = missions.find(m => m.mission_id === selectedId);

  const handleRerun = async () => {
    if (!selectedMeta) return;
    try {
      await startMission(`Help ${selectedMeta.entity_name}`, selectedMeta.entity_name);
    } catch { /* ignore */ }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      startPosX: position.x,
      startPosY: position.y,
    };
    const handleMouseMove = (ev: MouseEvent) => {
      if (!dragRef.current) return;
      setPosition({
        x: dragRef.current.startPosX + (ev.clientX - dragRef.current.startX),
        y: dragRef.current.startPosY + (ev.clientY - dragRef.current.startY),
      });
    };
    const handleMouseUp = () => {
      dragRef.current = null;
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  const handleResizeDown = (e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startY = e.clientY;
    const startW = size.width;
    const startH = size.height;
    const handleMouseMove = (ev: MouseEvent) => {
      setSize({
        width: Math.max(500, Math.min(1100, startW + (ev.clientX - startX))),
        height: Math.max(360, Math.min(900, startH + (ev.clientY - startY))),
      });
    };
    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed flex flex-col z-[99999]"
      style={{
        left: position.x,
        top: position.y,
        width: size.width,
        height: isMinimized ? 'auto' : size.height,
        border: '3px solid #333',
        backgroundColor: '#0a0a0a',
        boxShadow: '8px 8px 0px 0px rgba(0,0,0,0.4)',
      }}
    >
      {/* Title bar — drag handle */}
      <div
        onMouseDown={handleMouseDown}
        className="flex items-center justify-between px-3 py-2 border-b border-[#333] bg-black/80 cursor-move select-none"
      >
        <div className="flex items-center gap-2">
          <GripVertical size={14} className="text-gray-600" />
          <FileText size={16} className="text-[#00ff88]" />
          <span className="text-sm font-black uppercase tracking-widest text-[#00ff88]">Mission History</span>
          <span className="text-[10px] text-gray-500 ml-1">{missions.length} missions</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setIsMinimized(!isMinimized)}
            className="p-1 hover:bg-[#333] transition-colors rounded"
          >
            {isMinimized ? <Maximize2 size={12} className="text-gray-500" /> : <Minimize2 size={12} className="text-gray-500" />}
          </button>
          <button
            onClick={onClose}
            className="p-1 hover:bg-[#ff003c] hover:text-white transition-colors rounded"
          >
            <X size={14} className="text-gray-500 hover:text-white" />
          </button>
        </div>
      </div>

      {!isMinimized && (
        <div className="flex flex-1 overflow-hidden">
          {/* Left column — mission list */}
          <div className="w-[260px] shrink-0 border-r border-[#222] flex flex-col bg-black/40">
            <div className="p-2 border-b border-[#222]">
              <div className="relative">
                <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" />
                <input
                  type="text"
                  placeholder="Filter..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="w-full bg-[#111] border border-[#333] text-[11px] text-[#eee] py-1.5 pl-7 pr-2 outline-none focus:border-[#00ff88] placeholder:text-gray-600"
                />
              </div>
            </div>
            <div className="flex-1 overflow-y-auto">
              {!loading && filtered.length === 0 && (
                <div className="p-4 text-center text-gray-600 text-[11px]">No missions found.</div>
              )}
              {filtered.map(m => (
                <button
                  key={m.mission_id}
                  onClick={() => setSelectedId(m.mission_id)}
                  className={`w-full text-left px-3 py-2.5 border-b border-[#1a1a1a] hover:bg-[#151515] transition-colors flex items-center justify-between gap-2 ${
                    selectedId === m.mission_id ? 'bg-[#151515] border-l-2 border-l-[#00ff88]' : ''
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-[12px] font-bold truncate">{m.entity_name}</div>
                    <div className="flex items-center gap-1.5 text-[10px] text-gray-500 mt-0.5">
                      <Clock size={9} />
                      <span>{relativeTime(m.timestamp)}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className={`text-[9px] px-1 py-0.5 border uppercase font-bold ${
                      STATUS_COLORS[m.status] || 'text-gray-500 border-gray-500'
                    }`}>
                      {m.status === 'completed' ? 'OK' : m.status === 'failed' ? 'ERR' : m.status?.slice(0, 3)}
                    </span>
                    <ChevronRight size={12} className="text-gray-600" />
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Right column — report viewer */}
          <div className="flex-1 overflow-y-auto bg-[#0a0a0a]">
            {!selectedId && (
              <div className="flex items-center justify-center h-full text-gray-600 text-[12px]">
                Select a mission to view report
              </div>
            )}
            {detailLoading && (
              <div className="flex items-center justify-center h-full gap-2 text-gray-500 text-[12px]">
                <Loader2 size={14} className="animate-spin" />
                Loading...
              </div>
            )}
            {detail && !detailLoading && (
              <div className="p-4 max-w-3xl">
                <div className="flex items-start justify-between mb-4 pb-3 border-b border-[#333]">
                  <div>
                    <h2 className="text-base font-black text-white">{detail.entity_name}</h2>
                    <div className="flex items-center gap-2 mt-1 text-[11px] text-gray-500">
                      <span>{formatDate(detail.timestamp)}</span>
                      <span className={`text-[9px] px-1 py-0.5 border uppercase font-bold ${
                        STATUS_COLORS[detail.status] || 'text-gray-500 border-gray-500'
                      }`}>{detail.status}</span>
                    </div>
                  </div>
                  <button
                    onClick={handleRerun}
                    className="flex items-center gap-1 px-2.5 py-1 bg-[#00ff88]/10 text-[#00ff88] border border-[#00ff88]/30 text-[11px] hover:bg-[#00ff88]/20 transition-colors"
                    title="Run new mission for this entity"
                  >
                    <RotateCcw size={11} />
                    Re-run
                  </button>
                </div>
                <div className="prose prose-invert prose-sm max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {detail.report || '*No report content*'}
                  </ReactMarkdown>
                </div>
              </div>
            )}
          </div>

          {/* Resize handle */}
          <div
            onMouseDown={handleResizeDown}
            className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize"
            style={{ background: 'linear-gradient(135deg, transparent 50%, #444 50%)' }}
          />
        </div>
      )}
    </div>
  );
}
