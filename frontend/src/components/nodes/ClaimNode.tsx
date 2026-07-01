import { Handle, Position } from '@xyflow/react'

const SEVERITY_COLORS = {
  high: '#ef4444',
  medium: '#f97316',
  low: '#eab308',
}

const THREAD_COLORS = {
  intra_source: '#ef4444',
  inter_source: '#f97316',
  legal: '#3b82f6',
}

export function ClaimNode({ data, id }: any) {
  const { excerpt, source, speaker, threads = [], isLaw } = data

  const threadCounts = {
    intra_source: threads.filter((t: string) => t.startsWith('intra')).length,
    inter_source: threads.filter((t: string) => t.startsWith('inter')).length,
    legal: threads.filter((t: string) => t.startsWith('legal')).length,
  }

  const hasThreads = Object.values(threadCounts).some((c) => c > 0)
  const maxKind = Object.entries(threadCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'inter_source'

  return (
    <div
      className="brutalist-card"
      style={{
        width: isLaw ? 200 : 280,
        padding: '12px',
        border: isLaw ? '2px dashed #3b82f6' : `1px solid ${hasThreads ? THREAD_COLORS[maxKind as keyof typeof THREAD_COLORS] : '#333'}`,
        background: isLaw ? 'rgba(59, 130, 246, 0.08)' : 'rgba(0, 0, 0, 0.85)',
        position: 'relative',
      }}
    >
      {!isLaw && (
        <Handle type="target" position={Position.Left} style={{ background: '#555', width: 8, height: 8 }} />
      )}
      <Handle type="source" position={Position.Right} style={{ background: '#555', width: 8, height: 8 }} />

      <div style={{ fontSize: 10, color: '#888', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>
        {isLaw ? '⚖️ Legal Framework' : speaker}
        {!isLaw && <span style={{ marginLeft: 8, color: '#555' }}>({source})</span>}
      </div>

      <div style={{ fontSize: 12, color: '#eee', lineHeight: 1.4, marginBottom: 6 }}>
        {isLaw ? excerpt : `"${excerpt}"`}
      </div>

      {hasThreads && (
        <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
          {threadCounts.intra_source > 0 && (
            <span style={{ fontSize: 10, color: THREAD_COLORS.intra_source }}>
              ● {threadCounts.intra_source} same
            </span>
          )}
          {threadCounts.inter_source > 0 && (
            <span style={{ fontSize: 10, color: THREAD_COLORS.inter_source }}>
              ● {threadCounts.inter_source} conflict
            </span>
          )}
          {threadCounts.legal > 0 && (
            <span style={{ fontSize: 10, color: THREAD_COLORS.legal }}>
              ● {threadCounts.legal} legal
            </span>
          )}
        </div>
      )}

      <div style={{ fontSize: 9, color: '#555', marginTop: 4 }}>
        {id}
      </div>
    </div>
  )
}
