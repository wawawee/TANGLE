import { useEffect, useRef, useState } from 'react';

interface EntityInfo {
  entity_name: string;
  mission_count: number;
  entry_count: number;
  last_mission_ts: string | null;
  last_upload_ts: string | null;
}

interface Props {
  activeEntity: string | null;
  onSelectEntity: (entity: string) => void;
  onStartMission: (entity: string) => void;
}

function guessIcon(entity: string): string {
  const lower = entity.toLowerCase();
  if (lower.includes('cat') || lower.includes('katt') || lower.includes('luna')) return '🐱';
  if (lower.includes('dog') || lower.includes('hund')) return '🐕';
  if (lower.includes('inc') || lower.includes('corp') || lower.includes('ab') || lower.includes('ltd')) return '🏢';
  return '🎯';
}

function formatTs(ts: string | null): string {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return '—';
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    return d.toLocaleDateString();
  } catch {
    return ts;
  }
}

export default function EntitySelector({ activeEntity, onSelectEntity, onStartMission }: Props) {
  const [entities, setEntities] = useState<EntityInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchEntities = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/entities');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setEntities(json.entities || []);
      setErrorMsg('');
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load entities');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEntities();
    // Poll every 10s to pick up new entities
    pollRef.current = setInterval(fetchEntities, 10000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const filtered = search
    ? entities.filter(e => e.entity_name.toLowerCase().includes(search.toLowerCase()))
    : entities;

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', padding: 8 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, padding: '4px 8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12 }}>🎯</span>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text)' }}>
            Entities
          </span>
          <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>
            {entities.length}
          </span>
        </div>
        <button
          onClick={fetchEntities}
          style={{
            fontSize: 9, fontWeight: 700, padding: '3px 8px', borderRadius: 8,
            border: '1px solid var(--border)', background: 'transparent',
            color: 'var(--text-dim)', cursor: 'pointer',
          }}
        >
          ↻
        </button>
      </div>

      {/* Search */}
      <input
        type="text"
        value={search}
        onChange={e => setSearch(e.target.value)}
        placeholder="Search entities…"
        style={{
          marginBottom: 8, padding: '6px 10px', borderRadius: 8, fontSize: 10,
          background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
          color: 'var(--text)', outline: 'none', fontFamily: 'inherit',
        }}
      />

      {/* Error state */}
      {errorMsg && (
        <div style={{
          padding: 8, marginBottom: 8, borderRadius: 8,
          background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)',
          fontSize: 9, color: '#ef4444', textAlign: 'center',
        }}>
          {errorMsg}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: 'var(--cyan)', animation: 'pulse-glow 1s ease-in-out infinite',
          }} />
          <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 8 }}>Loading…</span>
        </div>
      )}

      {/* Entity list */}
      {!loading && (
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {filtered.length === 0 && (
            <div style={{ fontSize: 10, color: 'var(--text-muted)', padding: 16, textAlign: 'center' }}>
              {search ? 'No matching entities' : 'No entities yet. Upload a file or run a mission.'}
            </div>
          )}
          {filtered.map(ent => {
            const isActive = ent.entity_name === activeEntity;
            return (
              <div
                key={ent.entity_name}
                onClick={() => onSelectEntity(ent.entity_name)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer',
                  padding: '8px 10px', borderRadius: 10, marginBottom: 4,
                  transition: 'all 0.15s',
                  background: isActive ? 'rgba(139,92,246,0.12)' : 'transparent',
                  border: isActive ? '1px solid rgba(139,92,246,0.3)' : '1px solid transparent',
                }}
              >
                <span style={{ fontSize: 22, flexShrink: 0 }}>{guessIcon(ent.entity_name)}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 12, fontWeight: 700, color: isActive ? '#c084fc' : 'var(--text)',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>
                    {ent.entity_name}
                  </div>
                  <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2 }}>
                    {ent.mission_count} mission{ent.mission_count !== 1 ? 's' : ''}
                    {' · '}{ent.entry_count} file{ent.entry_count !== 1 ? 's' : ''}
                    {' · '}{formatTs(ent.last_mission_ts || ent.last_upload_ts)}
                  </div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); onStartMission(ent.entity_name); }}
                  title={`Run mission for ${ent.entity_name}`}
                  style={{
                    fontSize: 9, fontWeight: 700, padding: '4px 10px', borderRadius: 8,
                    border: '1px solid rgba(139,92,246,0.3)',
                    background: 'rgba(139,92,246,0.12)', color: '#c084fc',
                    cursor: 'pointer', flexShrink: 0,
                    textTransform: 'uppercase', letterSpacing: '0.05em',
                  }}
                >
                  Run
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}