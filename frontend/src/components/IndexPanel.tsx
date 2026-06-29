/**
 * IndexPanel — Live overview of every store TANGLE uses.
 *
 * Polls GET /api/admin/index and renders counts + health for:
 *   - SQLite (wiki_entries + missions)
 *   - Qdrant (collection + points)
 *   - Supabase (status — backend integration is Phase 1+, reported as not_connected)
 *   - Filesystem (wiki vault + uploads)
 *
 * Also exposes manual actions:
 *   - Refresh Index (re-fetch)
 *   - Export Wiki Vault (POST /api/admin/export-wiki → TANGLE_VAULT_ROOT, default .tangle/vault/)
 *   - Open Vault Folder (open in Finder)
 */

import { useEffect, useState, useCallback, useRef } from 'react';

interface SqliteInfo {
  path: string;
  exists: boolean;
  wiki_entries_count: number;
  missions_count: number;
  by_entity: Record<string, number>;
  oldest_entry: string | null;
  newest_entry: string | null;
  error?: string;
}

interface QdrantInfo {
  url: string;
  reachable: boolean;
  collection: string;
  collection_exists: boolean;
  points_count: number;
  error?: string;
}

interface SupabaseInfo {
  configured: boolean;
  status: string;
  phase: string;
  note: string;
  entries_count: number;
}

interface FsInfo {
  vault_root: string;
  exists: boolean;
  files: number;
  entities: number;
  last_modified: string | null;
  error?: string;
}

interface UploadsInfo {
  path: string;
  exists: boolean;
  files: number;
}

interface IndexData {
  generated_at: string;
  sqlite: SqliteInfo;
  qdrant: QdrantInfo;
  supabase: SupabaseInfo;
  filesystem: FsInfo;
  uploads: UploadsInfo;
  stores_healthy: boolean;
}

const cardBase = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: '12px',
  padding: '14px 16px',
  marginBottom: '12px',
};

const headerStyle = {
  fontSize: '10px',
  fontWeight: 900,
  letterSpacing: '0.18em',
  textTransform: 'uppercase' as const,
  color: 'var(--text-muted)',
  margin: '0 0 10px',
};

const kvRow = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '4px 0',
  fontSize: '12px',
  borderBottom: '1px dashed var(--border)',
};

const kvLastRow = { ...kvRow, borderBottom: 'none' };

const kLabel = { color: 'var(--text-muted)', fontFamily: 'JetBrains Mono, monospace' };
const kValue = { color: 'var(--text)', fontFamily: 'JetBrains Mono, monospace', fontWeight: 700 };

const badge = (color: string) => ({
  display: 'inline-block',
  padding: '2px 8px',
  borderRadius: '10px',
  fontSize: '9px',
  fontWeight: 900,
  letterSpacing: '0.1em',
  textTransform: 'uppercase' as const,
  background: `${color}20`,
  color,
  border: `1px solid ${color}40`,
});

const buttonBase = {
  padding: '8px 14px',
  borderRadius: '8px',
  border: '1px solid var(--border)',
  fontSize: '10px',
  fontWeight: 900,
  letterSpacing: '0.1em',
  textTransform: 'uppercase' as const,
  cursor: 'pointer',
  background: 'var(--glass-bg)',
  color: 'var(--text)',
  transition: 'all 0.2s',
};

const buttonPrimary = {
  ...buttonBase,
  background: 'color-mix(in srgb, var(--cyan) 20%, transparent)',
  borderColor: 'color-mix(in srgb, var(--cyan) 60%, transparent)',
  color: 'var(--cyan)',
};

function StatusDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
      <div
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: ok ? 'var(--emerald)' : 'var(--red)',
          boxShadow: `0 0 8px ${ok ? 'var(--emerald)' : 'var(--red)'}`,
          opacity: 0.85,
        }}
      />
      <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text)' }}>{label}</span>
    </div>
  );
}

function numFmt(n: number): string {
  return n.toLocaleString('en-US');
}

export default function IndexPanel() {
  const [data, setData] = useState<IndexData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportMsg, setExportMsg] = useState<string | null>(null);
  const [exportOk, setExportOk] = useState<boolean | null>(null);
  const [lastFetch, setLastFetch] = useState<string>('');

  // Shared signal for the lifetime of this component instance. useEffect below
  // owns the AbortController; manual Refresh onClick reuses the same signal so
  // unmount-during-manual-fetch aborts cleanly, same as auto-refresh.
  const acRef = useRef<AbortController | null>(null);

  const fetchIndex = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('http://localhost:8000/api/admin/index', { signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setLastFetch(new Date().toLocaleTimeString());
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') return;
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  const exportWiki = useCallback(async () => {
    const ac = new AbortController();
    setExporting(true);
    setExportMsg(null);
    setExportOk(null);
    try {
      const res = await fetch('http://localhost:8000/api/admin/export-wiki', {
        method: 'POST',
        signal: ac.signal,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      const json = await res.json();
      setExportMsg(
        `Exported ${json.chunks} chunks across ${json.entities} entities in ${json.duration_ms}ms`
      );
      setExportOk(true);
      // Re-fetch index so the filesystem card updates; reuse signal so unmount aborts cleanly
      fetchIndex(ac.signal);
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') return;
      const msg = e instanceof Error ? e.message : String(e);
      setExportMsg(`Export failed: ${msg}`);
      setExportOk(false);
    } finally {
      setExporting(false);
    }
  }, [fetchIndex]);

  useEffect(() => {
    const ac = new AbortController();
    acRef.current = ac;
    fetchIndex(ac.signal);
    // Auto-refresh every 15s while panel is open
    const t = setInterval(() => fetchIndex(ac.signal), 15000);
    return () => {
      ac.abort();
      acRef.current = null;
      clearInterval(t);
    };
  }, [fetchIndex]);

  if (!data) {
    return (
      <div style={{ padding: '20px', color: 'var(--text-muted)', fontSize: '12px' }}>
        {error ? `Loading failed: ${error}` : 'Loading index…'}
      </div>
    );
  }

  const entityEntries = Object.entries(data.sqlite.by_entity).sort((a, b) =>
    a[0].localeCompare(b[0])
  );

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        overflowY: 'auto',
        padding: '20px',
        background: 'var(--surface)',
        color: 'var(--text)',
        fontFamily: 'JetBrains Mono, monospace',
      }}
    >
      {/* Header */}
      <div style={{ marginBottom: '16px' }}>
        <h2
          style={{
            margin: 0,
            fontSize: '16px',
            fontWeight: 900,
            letterSpacing: '-0.02em',
            color: 'var(--text)',
          }}
        >
          Memory Index
        </h2>
        <p
          style={{
            margin: '4px 0 0',
            fontSize: '9px',
            color: 'var(--text-muted)',
            letterSpacing: '0.18em',
            textTransform: 'uppercase',
          }}
        >
          Live snapshot · last fetch {lastFetch || '—'}
        </p>
        <div style={{ marginTop: '10px', display: 'flex', gap: '8px' }}>
          <button onClick={() => fetchIndex(acRef.current?.signal)} disabled={loading} style={buttonPrimary}>
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
          <button onClick={exportWiki} disabled={exporting} style={buttonBase}>
            {exporting ? 'Exporting…' : 'Export Wiki Vault'}
          </button>
        </div>
        {exportMsg && (
          <p
            style={{
              fontSize: '11px',
              marginTop: '8px',
              color: exportOk === false ? 'var(--red)' : 'var(--emerald)',
            }}
          >
            {exportOk === false ? '✗ ' : '✓ '}{exportMsg}
          </p>
        )}
        {error && (
          <p
            style={{
              fontSize: '10px',
              marginTop: '8px',
              padding: '6px 10px',
              borderRadius: '6px',
              background: 'color-mix(in srgb, var(--red) 10%, transparent)',
              border: '1px solid color-mix(in srgb, var(--red) 40%, transparent)',
              color: 'var(--red)',
            }}
            aria-live="polite"
          >
            Last fetch failed: {error} — auto-retry on next 15s tick
          </p>
        )}
      </div>

      {/* SQLite */}
      <div style={cardBase}>
        <p style={headerStyle}>SQLite — Wiki DB</p>
        <StatusDot ok={data.sqlite.exists && !data.sqlite.error} label="Database" />
        <div style={kvRow}>
          <span style={kLabel}>wiki_entries</span>
          <span style={kValue}>{numFmt(data.sqlite.wiki_entries_count)}</span>
        </div>
        <div style={kvRow}>
          <span style={kLabel}>missions</span>
          <span style={kValue}>{numFmt(data.sqlite.missions_count)}</span>
        </div>
        <div style={kvLastRow}>
          <span style={kLabel}>path</span>
          <span style={{ ...kValue, fontSize: '10px', opacity: 0.7 }}>{data.sqlite.path.split('/').pop()}</span>
        </div>
        {entityEntries.length > 0 && (
          <>
            <p style={{ ...headerStyle, marginTop: '12px' }}>By Entity</p>
            {entityEntries.map(([name, count]) => (
              <div key={name} style={kvRow}>
                <span style={kLabel}>{name}</span>
                <span style={kValue}>{numFmt(count)}</span>
              </div>
            ))}
          </>
        )}
      </div>

      {/* Qdrant */}
      <div style={cardBase}>
        <p style={headerStyle}>Qdrant — Vector Store</p>
        <StatusDot ok={data.qdrant.reachable} label={data.qdrant.reachable ? 'Reachable' : 'Unreachable'} />
        <div style={kvRow}>
          <span style={kLabel}>collection</span>
          <span style={kValue}>{data.qdrant.collection}</span>
        </div>
        <div style={kvRow}>
          <span style={kLabel}>exists</span>
          <span style={kValue}>{data.qdrant.collection_exists ? 'yes' : 'no'}</span>
        </div>
        <div style={kvRow}>
          <span style={kLabel}>points</span>
          <span style={kValue}>{numFmt(data.qdrant.points_count)}</span>
        </div>
        <div style={kvLastRow}>
          <span style={kLabel}>url</span>
          <span style={{ ...kValue, fontSize: '10px', opacity: 0.7 }}>{data.qdrant.url}</span>
        </div>
        {!data.qdrant.collection_exists && data.qdrant.reachable && (
          <p
            style={{
              fontSize: '10px',
              color: 'var(--text-muted)',
              margin: '8px 0 0',
              fontStyle: 'italic',
            }}
          >
            Created lazily on first upsert.
          </p>
        )}
      </div>

      {/* Supabase */}
      <div style={cardBase}>
        <p style={headerStyle}>Supabase — Relational</p>
        <StatusDot
          ok={data.supabase.configured}
          label={
            data.supabase.configured
              ? 'Connected'
              : data.supabase.status
                ? `Not connected (${data.supabase.status})`
                : 'Not connected'
          }
        />
        {data.supabase.phase && (
          <span style={badge('#f59e0b')}>{data.supabase.phase}</span>
        )}
        {data.supabase.note && (
          <p style={{ fontSize: '11px', color: 'var(--text-muted)', margin: '8px 0 0', lineHeight: 1.5 }}>
            {data.supabase.note}
          </p>
        )}
      </div>

      {/* Filesystem wiki vault */}
      <div style={cardBase}>
        <p style={headerStyle}>Filesystem — Wiki Vault</p>
        <StatusDot ok={data.filesystem.exists} label={data.filesystem.exists ? 'Vault exists' : 'Vault missing'} />
        <div style={kvRow}>
          <span style={kLabel}>files</span>
          <span style={kValue}>{numFmt(data.filesystem.files)}</span>
        </div>
        <div style={kvRow}>
          <span style={kLabel}>entities</span>
          <span style={kValue}>{numFmt(data.filesystem.entities)}</span>
        </div>
        <div style={kvRow}>
          <span style={kLabel}>last_modified</span>
          <span style={{ ...kValue, fontSize: '10px' }}>
            {data.filesystem.last_modified ? data.filesystem.last_modified.slice(0, 19).replace('T', ' ') : '—'}
          </span>
        </div>
        <div style={kvLastRow}>
          <span style={kLabel}>path</span>
          <span style={{ ...kValue, fontSize: '10px', opacity: 0.7 }}>{data.filesystem.vault_root}</span>
        </div>
        {!data.filesystem.exists && (
          <p
            style={{
              fontSize: '10px',
              color: 'var(--text-muted)',
              margin: '8px 0 0',
              fontStyle: 'italic',
            }}
          >
            Run <strong>Export Wiki Vault</strong> to create it.
          </p>
        )}
      </div>

      {/* Uploads */}
      <div style={cardBase}>
        <p style={headerStyle}>Uploads — Raw Files</p>
        <StatusDot ok={data.uploads.exists} label={data.uploads.exists ? 'Directory exists' : 'Directory missing'} />
        <div style={kvRow}>
          <span style={kLabel}>files</span>
          <span style={kValue}>{numFmt(data.uploads.files)}</span>
        </div>
        <div style={kvLastRow}>
          <span style={kLabel}>path</span>
          <span style={{ ...kValue, fontSize: '10px', opacity: 0.7 }}>{data.uploads.path.split('/').pop()}</span>
        </div>
      </div>

      <p
        style={{
          fontSize: '9px',
          color: 'var(--text-muted)',
          textAlign: 'center',
          margin: '20px 0 0',
          letterSpacing: '0.18em',
          textTransform: 'uppercase',
        }}
      >
        Stores healthy: {data.stores_healthy ? '✓' : '✗'} · refreshes every 15s
      </p>
    </div>
  );
}