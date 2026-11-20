import { Activity, ArrowRight, GitBranch, Route, ShieldAlert } from 'lucide-react'
import Workspace from './Workspace'

export default function RoutingResilience({ onOpenExperiments }: { onOpenExperiments: () => void }) {
  return <div className="space-y-4">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div><p className="text-xs uppercase tracking-[0.22em] text-teal-300">Routing behaviour</p><h2 className="mt-1 text-2xl font-semibold text-white">Routing & resilience</h2><p className="mt-1 text-sm text-slate-400">Inspect shortest-path decisions, then compare frozen and adaptive routing under controlled failures.</p></div>
      <button className="btn btn-primary" onClick={onOpenExperiments}><Activity className="h-4 w-4"/>Run resilience experiment <ArrowRight className="h-4 w-4"/></button>
    </div>
    <section className="grid gap-3 md:grid-cols-3">
      <div className="panel"><div className="flex items-center gap-2 text-sm font-semibold text-white"><Route className="h-4 w-4 text-teal-300"/>BFS baseline</div><p className="mt-2 text-xs leading-5 text-slate-400">Finds a minimum-hop route in an unweighted interpretation of the topology. Routing-cost weights are ignored.</p></div>
      <div className="panel"><div className="flex items-center gap-2 text-sm font-semibold text-white"><GitBranch className="h-4 w-4 text-violet-300"/>Static Dijkstra</div><p className="mt-2 text-xs leading-5 text-slate-400">Freezes one next-hop forwarding entry per router for the selected destination at simulation time zero. It does not adapt after failures.</p></div>
      <div className="panel"><div className="flex items-center gap-2 text-sm font-semibold text-white"><ShieldAlert className="h-4 w-4 text-amber-300"/>Dynamic Dijkstra</div><p className="mt-2 text-xs leading-5 text-slate-400">Recomputes a route from the packet's current router when a scheduled node or link event changes the topology.</p></div>
    </section>
    <Workspace module="routing"/>
  </div>
}
