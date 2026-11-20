import { useEffect, useState } from 'react'
import { Activity, ArrowRight, Database, Network, Send } from 'lucide-react'
import { api } from '../api'
import type { Analysis, GraphData } from '../types'
import type { ExperimentIndex } from '../api'

export type AppSection = 'dashboard' | 'network' | 'routing' | 'packet-transfer' | 'experiments' | 'results' | 'methodology'

export default function ResearchDashboard({ onNavigate }: { onNavigate: (section: AppSection) => void }) {
  const [graph, setGraph] = useState<GraphData | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [experiments, setExperiments] = useState<ExperimentIndex[]>([])
  const [health, setHealth] = useState<'online' | 'offline' | 'checking'>('checking')
  useEffect(() => {
    let mounted = true
    Promise.all([api.health(), api.getGraph(), api.analysis(), api.experiments()])
      .then(([_, g, a, e]) => { if (mounted) { setGraph(g); setAnalysis(a); setExperiments(e.experiments); setHealth('online') } })
      .catch(() => { if (mounted) setHealth('offline') })
    return () => { mounted = false }
  }, [])
  const cards = [
    { label: 'Network nodes', value: analysis?.node_count ?? '—', icon: Network },
    { label: 'Network links', value: analysis?.edge_count ?? '—', icon: Activity },
    { label: 'Components', value: analysis?.component_count ?? '—', icon: Database },
    { label: 'Saved comparisons', value: experiments.length, icon: Send },
  ]
  return <div className="space-y-5">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div><p className="text-xs uppercase tracking-[0.22em] text-teal-300">Research workspace</p><h2 className="mt-1 text-2xl font-semibold text-white">Network overview</h2><p className="mt-1 text-sm text-slate-400">Model a topology, simulate routing under failures, and inspect reproducible experiment results.</p></div>
      <span className={`badge ${health === 'online' ? 'bg-emerald-900 text-emerald-200' : health === 'offline' ? 'bg-rose-900 text-rose-200' : 'bg-slate-700 text-slate-200'}`}>{health === 'online' ? 'Backend connected' : health === 'offline' ? 'Backend disconnected' : 'Checking backend'}</span>
    </div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{cards.map(({ label, value, icon: Icon }) => <div className="panel" key={label}><div className="flex items-center justify-between"><span className="text-xs text-slate-400">{label}</span><Icon className="h-4 w-4 text-teal-300" /></div><div className="mt-3 text-3xl font-semibold text-white">{value}</div></div>)}</div>
    <div className="grid gap-4 xl:grid-cols-5">
      <section className="panel xl:col-span-3"><div className="flex items-center justify-between"><div><h3 className="text-sm font-semibold text-white">Active topology</h3><p className="text-xs text-slate-400">The shared network graph currently held by the backend</p></div><button className="btn" onClick={() => onNavigate('network')}>Open Network Studio <ArrowRight className="h-4 w-4" /></button></div>
        {graph && <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">{graph.nodes.slice(0, 8).map((n) => <div key={n.id} className="rounded-lg border border-navy-600 bg-navy-900 px-3 py-2 text-xs"><span className="mr-2 inline-block h-2 w-2 rounded-full bg-teal-400" />{n.id}</div>)}</div>}
        {analysis && <div className="mt-4 flex flex-wrap gap-2 text-xs"><span className="badge bg-slate-700 text-slate-200">{analysis.connected ? 'Connected topology' : 'Disconnected topology'}</span><span className="badge bg-slate-700 text-slate-200">{analysis.isolated_nodes.length} isolated nodes</span><span className="badge bg-slate-700 text-slate-200">Graph version {analysis.version}</span></div>}
      </section>
      <section className="panel xl:col-span-2"><h3 className="text-sm font-semibold text-white">Research workflow</h3><div className="mt-3 space-y-3">
        {[['01','Prepare a topology','Add nodes, links, routing cost and link characteristics.','network'],['02','Transfer mixed traffic','Create DATA, ACK, CONTROL, VOICE and VIDEO packets and watch their route.','packet-transfer'],['03','Inspect research evidence','Review paired results, confidence intervals and saved run provenance.','results']].map(([n,title,desc,section]) => <button key={n} onClick={() => onNavigate(section as AppSection)} className="flex w-full gap-3 rounded-lg border border-navy-600 bg-navy-900 p-3 text-left hover:border-teal-500"><span className="mono text-xs text-teal-300">{n}</span><span><b className="block text-sm text-slate-100">{title}</b><span className="mt-1 block text-xs text-slate-400">{desc}</span></span></button>)}
      </div></section>
    </div>
    <section className="panel"><div className="flex items-center justify-between"><div><h3 className="text-sm font-semibold text-white">Recent experiment comparisons</h3><p className="text-xs text-slate-400">Persisted in the local SQLite research database</p></div><button className="btn" onClick={() => onNavigate('results')}>View results <ArrowRight className="h-4 w-4" /></button></div>
      {experiments.length ? <div className="mt-3 divide-y divide-navy-600">{experiments.slice(0, 5).map((e) => <div key={e.comparison_id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"><span className="mono text-xs text-slate-300">{e.comparison_id.slice(0, 12)}…</span><span className="text-xs text-slate-400">{e.run_count} runs · {new Date(e.created_at).toLocaleString()}</span></div>)}</div> : <p className="mt-4 text-sm text-slate-400">No saved experiments yet. Configure the first comparison in Experiments.</p>}
    </section>
  </div>
}
