import { useEffect, useMemo, useState } from 'react'
import { Download, RefreshCw } from 'lucide-react'
import { api } from '../api'
import type { ExperimentDetail, ExperimentIndex, PacketOutcomePage, ResearchAlgorithm } from '../api'

const labels: Record<ResearchAlgorithm, string> = { bfs: 'BFS', dijkstra_static: 'Static Dijkstra', dijkstra_dynamic: 'Dynamic Dijkstra' }
function saveFile(name: string, data: string, type: string) { const url = URL.createObjectURL(new Blob([data], { type })); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url) }
function metricValue(metric: { mean: number | null }, key: string) { if (metric.mean === null) return 'N/A'; return key === 'packet_delivery_ratio' ? `${(metric.mean * 100).toFixed(2)}%` : metric.mean.toFixed(4) }
function confidence(metric: { ci95: [number, number] | null }, key: string) { if (!metric.ci95) return 'Not available'; const scale = key === 'packet_delivery_ratio' ? 100 : 1; return `[${(metric.ci95[0] * scale).toFixed(4)}, ${(metric.ci95[1] * scale).toFixed(4)}]` }
export default function ResearchResults({ selectedId }: { selectedId?: string | null }) {
  const [index, setIndex] = useState<ExperimentIndex[]>([])
  const [selected, setSelected] = useState<string>('')
  const [detail, setDetail] = useState<ExperimentDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [packetRun, setPacketRun] = useState<string | null>(null)
  const [packetOffset, setPacketOffset] = useState(0)
  const [packetPage, setPacketPage] = useState<PacketOutcomePage | null>(null)
  const [packetLoading, setPacketLoading] = useState(false)
  const refresh = async () => { try { const r = await api.experiments(); setIndex(r.experiments); setError(null) } catch (e) { setError(e instanceof Error ? e.message : String(e)) } }
  useEffect(() => { void refresh() }, [])
  useEffect(() => { if (selectedId) setSelected(selectedId); else if (!selected && index[0]) setSelected(index[0].comparison_id) }, [selectedId, index, selected])
  useEffect(() => { if (!selected) { setDetail(null); return } setPacketRun(null); setPacketOffset(0); api.experiment(selected).then(setDetail).catch((e) => setError(e instanceof Error ? e.message : String(e))) }, [selected])
  useEffect(() => {
    if (!packetRun) { setPacketPage(null); return }
    let cancelled = false
    setPacketLoading(true)
    api.packetOutcomes(packetRun, packetOffset, 50).then((page) => { if (!cancelled) setPacketPage(page) })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : String(e)) })
      .finally(() => { if (!cancelled) setPacketLoading(false) })
    return () => { cancelled = true }
  }, [packetRun, packetOffset])
  const grouped = useMemo(() => {
    const by: Record<string, { algorithm: string; pdr: number[]; throughput: number[]; latency: number[] }> = {}
    for (const run of detail?.runs ?? []) {
      const k = run.algorithm; by[k] ??= { algorithm: labels[run.algorithm], pdr: [], throughput: [], latency: [] }
      const m = run.result.metrics
      if (typeof m.packet_delivery_ratio === 'number') by[k].pdr.push(m.packet_delivery_ratio * 100)
      if (typeof m.throughput_mbps === 'number') by[k].throughput.push(m.throughput_mbps)
      if (typeof m.mean_latency_ms === 'number') by[k].latency.push(m.mean_latency_ms)
    }
    return Object.values(by).map((x) => ({ algorithm: x.algorithm, runs: x.pdr.length, pdr: avg(x.pdr), throughput: avg(x.throughput), latency: avg(x.latency) }))
  }, [detail])
  const exportCsv = () => {
    if (!detail) return
    const cols = ['algorithm','repetition','seed','packet_delivery_ratio','packet_loss_ratio','throughput_mbps','mean_latency_ms','median_latency_ms','p95_latency_ms','route_recovery_ms','route_recalculations','mean_signing_time_ms','mean_verification_time_ms']
    const rows = detail.runs.map((r) => cols.map((c) => c in r ? String((r as unknown as Record<string, unknown>)[c] ?? '') : String(r.result.metrics[c] ?? '')).join(','))
    saveFile(`irsd-${selected}.csv`, [cols.join(','), ...rows].join('\n'), 'text/csv')
  }
  return <div className="space-y-5">
    <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs uppercase tracking-[0.22em] text-teal-300">Research evidence</p><h2 className="mt-1 text-2xl font-semibold text-white">Results & analytics</h2><p className="mt-1 text-sm text-slate-400">Browse saved experiment groups and inspect per-run metrics and provenance.</p></div><button className="btn" onClick={() => void refresh()}><RefreshCw className="h-4 w-4"/>Refresh</button></div>
    {error && <div className="rounded border border-rose-700 bg-rose-950 p-3 text-sm text-rose-200">{error}</div>}
    <div className="grid gap-4 xl:grid-cols-4"><aside className="panel xl:col-span-1"><h3 className="text-sm font-semibold text-white">Saved comparisons</h3>{index.length ? <div className="mt-3 space-y-2">{index.map((e) => <button key={e.comparison_id} onClick={() => setSelected(e.comparison_id)} className={`w-full rounded-lg border p-3 text-left ${selected === e.comparison_id ? 'border-teal-500 bg-teal-950/30' : 'border-navy-600 bg-navy-900'}`}><div className="mono text-xs text-slate-200">{e.comparison_id.slice(0, 14)}…</div><div className="mt-1 text-xs text-slate-400">{e.run_count} runs · {new Date(e.created_at).toLocaleString()}</div></button>)}</div> : <p className="mt-3 text-xs text-slate-400">No saved experiment comparisons.</p>}</aside>
      <section className="panel xl:col-span-3"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-sm font-semibold text-white">Comparison detail</h3>{detail && <div className="flex gap-2"><button className="btn" onClick={exportCsv}><Download className="h-4 w-4"/>CSV</button><button className="btn" onClick={() => saveFile(`irsd-${selected}.json`, JSON.stringify(detail, null, 2), 'application/json')}><Download className="h-4 w-4"/>JSON</button></div>}</div>
        {!detail ? <p className="mt-8 text-center text-sm text-slate-500">Select a saved comparison to inspect it.</p> : <><div className="mt-3 grid gap-2 sm:grid-cols-3"><div className="rounded bg-navy-900 p-3"><div className="text-xs text-slate-400">Comparison ID</div><div className="mono mt-1 break-all text-xs">{detail.comparison_id}</div></div><div className="rounded bg-navy-900 p-3"><div className="text-xs text-slate-400">Runs recorded</div><div className="mt-1 text-2xl font-semibold">{detail.runs.length}</div></div><div className="rounded bg-navy-900 p-3"><div className="text-xs text-slate-400">Topology snapshot</div><div className="mt-1 text-sm">{detail.runs[0]?.topology.nodes.length ?? 0} nodes · {detail.runs[0]?.topology.edges.length ?? 0} links</div></div></div>
          <div className="mt-4 overflow-x-auto"><h4 className="mb-2 text-sm font-semibold text-white">Per-run observations</h4><table className="w-full min-w-[600px] text-left text-xs"><thead className="text-slate-400"><tr><th className="p-2">Algorithm</th><th>Repetition</th><th>Seed</th><th>PDR</th><th>Throughput</th><th>Mean latency</th><th>Route recovery</th><th>Packet outcomes</th></tr></thead><tbody>{detail.runs.map((r) => <tr className="border-t border-navy-600" key={r.run_id}><td className="p-2">{labels[r.algorithm]}</td><td>{r.repetition}</td><td>{r.seed}</td><td>{typeof r.result.metrics.packet_delivery_ratio === 'number' ? `${(r.result.metrics.packet_delivery_ratio * 100).toFixed(2)}%` : 'N/A'}</td><td>{fmt(r.result.metrics.throughput_mbps)}</td><td>{fmt(r.result.metrics.mean_latency_ms)}</td><td>{fmt(r.result.metrics.route_recovery_ms)}</td><td><button className="btn px-2 py-1 text-[11px]" onClick={() => { setPacketRun(r.run_id); setPacketOffset(0) }}>View {r.result.packet_outcome_count} packets</button></td></tr>)}</tbody></table></div>
          {packetRun && <div className="mt-4 rounded-lg border border-navy-600 bg-navy-900 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><div><h4 className="text-sm font-semibold text-white">Packet-level outcomes</h4><p className="text-xs text-slate-400">Paginated records for run {packetRun.slice(0, 14)}…</p></div><button className="btn" onClick={() => setPacketRun(null)}>Close</button></div>{packetLoading ? <p className="mt-3 text-xs text-slate-400">Loading packet outcomes…</p> : packetPage && <><div className="mt-3 overflow-x-auto"><table className="w-full min-w-[620px] text-left text-xs"><thead className="text-slate-400"><tr><th className="p-2">Packet</th><th>Status</th><th>Reason</th><th>Generated (ms)</th><th>Finished (ms)</th><th>Hops</th><th>Route history</th></tr></thead><tbody>{packetPage.packets.map((p) => <tr className="border-t border-navy-700" key={p.packet_id}><td className="p-2 mono">{p.packet_id}</td><td>{p.status}</td><td>{p.reason}</td><td>{p.generated_at_ms.toFixed(2)}</td><td>{p.finished_at_ms === null ? 'N/A' : p.finished_at_ms.toFixed(2)}</td><td>{p.hops}</td><td className="mono">{p.route_history.join(' → ') || '—'}</td></tr>)}</tbody></table></div><div className="mt-3 flex items-center justify-between text-xs text-slate-400"><span>{packetPage.total} total · showing {packetPage.total ? packetPage.offset + 1 : 0}–{Math.min(packetPage.offset + packetPage.packets.length, packetPage.total)}</span><div className="flex gap-2"><button className="btn" disabled={packetPage.offset === 0} onClick={() => setPacketOffset(Math.max(0, packetOffset - 50))}>Previous</button><button className="btn" disabled={packetPage.offset + packetPage.packets.length >= packetPage.total} onClick={() => setPacketOffset(packetOffset + 50)}>Next</button></div></div></>}</div>}
          <div className="mt-5 overflow-x-auto"><h4 className="mb-2 text-sm font-semibold text-white">Aggregated metrics (mean and 95% CI)</h4><table className="w-full min-w-[620px] text-left text-xs"><thead className="text-slate-400"><tr><th className="p-2">Algorithm</th><th>Metric</th><th>Mean</th><th>SD</th><th>95% CI</th><th>n</th></tr></thead><tbody>{Object.entries(detail.summaries).flatMap(([algorithm, metrics]) => Object.entries(metrics).filter(([key]) => ['packet_delivery_ratio','throughput_mbps','mean_latency_ms','p95_latency_ms','route_recovery_ms'].includes(key)).map(([key, metric]) => <tr className="border-t border-navy-600" key={`${algorithm}-${key}`}><td className="p-2">{labels[algorithm as ResearchAlgorithm]}</td><td>{key.replaceAll('_', ' ')}</td><td>{metricValue(metric, key)}</td><td>{metric.stddev === null ? 'N/A' : metric.stddev.toFixed(4)}</td><td>{confidence(metric, key)}</td><td>{metric.n}</td></tr>))}</tbody></table></div>
          {Object.keys(detail.paired_comparisons).length > 0 && <div className="mt-5 overflow-x-auto"><h4 className="mb-2 text-sm font-semibold text-white">Paired differences</h4><p className="mb-2 text-xs text-slate-400">Candidate minus reference ({labels[detail.reference_algorithm]}), paired by both repetition and seed.</p><table className="w-full min-w-[580px] text-left text-xs"><thead className="text-slate-400"><tr><th className="p-2">Candidate</th><th>Metric</th><th>Mean difference</th><th>95% CI</th><th>Matched n</th></tr></thead><tbody>{Object.entries(detail.paired_comparisons).flatMap(([algorithm, metrics]) => Object.entries(metrics).map(([key, metric]) => <tr className="border-t border-navy-600" key={`${algorithm}-${key}`}><td className="p-2">{labels[algorithm as ResearchAlgorithm]}</td><td>{key.replaceAll('_', ' ')}</td><td>{metric.mean === null ? 'N/A' : key === 'packet_delivery_ratio' ? `${(metric.mean * 100).toFixed(2)} pp` : metric.mean.toFixed(4)}</td><td>{confidence(metric, key)}</td><td>{metric.matched_repetitions}</td></tr>))}</tbody></table></div>}
          <div className="mt-4 grid gap-3 sm:grid-cols-3">{grouped.map((g) => <div className="rounded-lg border border-navy-600 bg-navy-900 p-3" key={g.algorithm}><div className="text-xs text-slate-400">{g.algorithm}</div><div className="mt-2 text-lg font-semibold">{g.pdr.toFixed(1)}% <span className="text-xs font-normal text-slate-500">PDR</span></div><div className="mt-1 text-xs text-slate-400">{g.throughput.toFixed(4)} Mbps · {g.latency.toFixed(3)} ms avg latency</div></div>)}</div>
          <p className="mt-4 text-xs text-slate-500">Detailed packet outcomes are stored with each run but omitted from this summary response. Application version: {detail.runtime_provenance.application_version ?? detail.runs[0]?.app_version ?? 'unknown'} · Python {detail.runtime_provenance.python_version ?? 'unknown'} · {detail.runtime_provenance.platform ?? 'platform unknown'}.</p>
        </>}
      </section>
    </div>
  </div>
}
function avg(values: number[]) { return values.length ? values.reduce((a,b) => a+b, 0) / values.length : 0 }
function fmt(v: unknown) { return typeof v === 'number' ? v.toFixed(4) : 'N/A' }
