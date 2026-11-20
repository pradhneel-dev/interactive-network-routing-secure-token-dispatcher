import type { DispatchBody, DispatchEvent, PacketResult, Report, Scenario, TraceStep } from './types'

export const edgeKey = (a: string, b: string) => (a < b ? `${a}||${b}` : `${b}||${a}`)

export interface TraceView {
  step: TraceStep | null
  visited: Set<string>
  processed: Set<string>
  frontier: Set<string>
  frontierLabels: string[]
  current: string | null
  edge: [string, string] | null
  explored: Set<string>
}

/** Derive everything the canvas/tables show from the REAL trace returned by the backend. idx -1 = not started. */
export function traceView(steps: TraceStep[], idx: number): TraceView {
  const empty: TraceView = { step: null, visited: new Set(), processed: new Set(), frontier: new Set(), frontierLabels: [], current: null, edge: null, explored: new Set() }
  if (idx < 0 || steps.length === 0) return empty
  const i = Math.min(idx, steps.length - 1)
  const step = steps[i]
  const explored = new Set<string>()
  for (let k = 0; k <= i; k++) {
    const e = steps[k].edge
    if (e) explored.add(edgeKey(e[0], e[1]))
  }
  const ids = step.frontier.map((f) => (Array.isArray(f) ? f[0] : f))
  const labels = step.frontier.map((f) => (Array.isArray(f) ? `${f[0]} (${f[1]})` : f))
  return { step, visited: new Set(step.visited), processed: new Set(step.processed), frontier: new Set(ids), frontierLabels: labels, current: step.current, edge: step.edge, explored }
}

export interface FrameState {
  event: DispatchEvent | null
  activeEdge: [string, string] | null
  positions: Record<number, string | null> // seq -> router currently holding the packet (null = lost)
  visibleEvents: DispatchEvent[]
}

/** Position of every packet after replaying events[0..idx]. */
export function frameState(events: DispatchEvent[], idx: number): FrameState {
  const positions: Record<number, string | null> = {}
  const upto = events.slice(0, idx + 1)
  for (const e of upto) {
    if (e.kind === 'dropped') positions[e.seq] = null
    else if (e.kind === 'send') positions[e.seq] = e.from
    else if (e.kind === 'hop' || e.kind === 'arrived') positions[e.seq] = e.to
  }
  const event = idx >= 0 ? events[Math.min(idx, events.length - 1)] ?? null : null
  const activeEdge = event && event.from && event.to && event.from !== event.to ? ([event.from, event.to] as [string, string]) : null
  return { event, activeEdge, positions, visibleEvents: upto }
}

export function scenarioToOptions(scenario: Record<number, Scenario>, dropCount: number): DispatchBody {
  const pick = (s: Scenario) => Object.entries(scenario).filter(([, v]) => v === s).map(([k]) => Number(k)).sort((a, b) => a - b)
  return {
    drop_seqs: pick('drop'), drop_count: dropCount, tamper_payload_seqs: pick('tamper_payload'),
    tamper_route_seqs: pick('tamper_route'), tamper_token_seqs: pick('tamper_token'), duplicate_seqs: pick('duplicate'),
  }
}

export function summarizeResults(results: PacketResult[]) {
  const count = (s: string) => results.filter((r) => r.status === s).length
  const sent = results.length
  const verified = count('Delivered & Verified')
  return {
    sent, received: results.filter((r) => r.received).length, lost: count('Lost/Missing'), verified,
    integrity: count('Payload Modified'), signature: count('Signature Invalid'), metadata: count('Metadata Tampered'),
    pct: sent ? Math.round((verified / sent) * 10000) / 100 : 0,
  }
}

export function reportMatchesResults(report: Report, results: PacketResult[]): boolean {
  const s = summarizeResults(results)
  return report.packets_sent === s.sent && report.packets_received === s.received && report.packets_lost === s.lost &&
    report.delivered_verified === s.verified && report.integrity_failures === s.integrity &&
    report.signature_failures === s.signature && report.metadata_failures === s.metadata && report.delivery_percentage === s.pct
}

export function circleLayout(ids: string[], cx = 420, cy = 250, r = 220): Record<string, { x: number; y: number }> {
  const out: Record<string, { x: number; y: number }> = {}
  ids.forEach((id, i) => {
    const a = (2 * Math.PI * i) / Math.max(ids.length, 1) - Math.PI / 2
    out[id] = { x: Math.round(cx + r * Math.cos(a)), y: Math.round(cy + r * 0.8 * Math.sin(a)) }
  })
  return out
}

export const fmt = (n: number | null | undefined) => (n === null || n === undefined ? '-' : Number.isInteger(n) ? String(n) : n.toFixed(2))
export const short = (v: string | number, n = 10) => { const s = String(v); return s.length > n ? `${s.slice(0, n)}...` : s }
