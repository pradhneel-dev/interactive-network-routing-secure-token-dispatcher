import { useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  Activity, BarChart3, BookOpen, FlaskConical, LayoutDashboard, Network,
  Route as RouteIcon, Send, Waypoints,
} from 'lucide-react'
import Workspace from './components/Workspace'
import RoutingResilience from './components/RoutingResilience'
import ResearchDashboard, { type AppSection } from './components/ResearchDashboard'
import PacketTransfer from './components/PacketTransfer'
import ResearchLab from './components/ResearchLab'
import ResearchResults from './components/ResearchResults'
import Methodology from './components/Methodology'
import { API_URL } from './api'

const NAV: { id: AppSection; label: string; icon: LucideIcon; group: string }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, group: 'Workspace' },
  { id: 'network', label: 'Network Studio', icon: Network, group: 'Workspace' },
  { id: 'routing', label: 'Routing & Resilience', icon: RouteIcon, group: 'Research' },
  { id: 'packet-transfer', label: 'Packet Transfer', icon: Send, group: 'Research' },
  { id: 'experiments', label: 'Experiments', icon: FlaskConical, group: 'Research' },
  { id: 'results', label: 'Results & Analytics', icon: BarChart3, group: 'Research' },
  { id: 'methodology', label: 'Methodology', icon: BookOpen, group: 'Reference' },
]

export default function App() {
  const [section, setSection] = useState<AppSection>('dashboard')
  const [selectedExperiment, setSelectedExperiment] = useState<string | null>(null)
  const navigate = (next: AppSection) => setSection(next)
  return <div className="min-h-screen bg-navy-950 text-slate-200">
    <header className="sticky top-0 z-20 border-b border-navy-600 bg-navy-950/95 px-4 py-3 backdrop-blur md:px-6">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-teal-500/40 bg-teal-500/10"><Waypoints className="h-5 w-5 text-teal-300"/></div>
        <div><h1 className="text-base font-semibold tracking-wide text-white">IRSD <span className="font-normal text-slate-400">/ Research Platform</span></h1><p className="text-[11px] text-slate-500">Network routing · resilience · packet transfer</p></div>
        <div className="ml-auto hidden items-center gap-2 text-xs text-slate-500 sm:flex"><Activity className="h-3.5 w-3.5 text-emerald-400"/>Local simulation <span className="mx-1 text-slate-700">|</span> API {API_URL}</div>
      </div>
    </header>
    <div className="mx-auto flex max-w-[1800px]">
      <aside className="sticky top-[65px] hidden h-[calc(100vh-65px)] w-64 shrink-0 border-r border-navy-700 bg-navy-950/80 p-3 lg:block">
        <p className="px-3 pb-2 pt-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-600">Workspace</p>
        {NAV.filter((x) => x.group === 'Workspace').map(({ id, label, icon: Icon }) => <button key={id} onClick={() => navigate(id)} className={`mb-1 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition ${section === id ? 'border border-teal-500/30 bg-teal-500/10 text-teal-200' : 'text-slate-400 hover:bg-navy-800 hover:text-white'}`}><Icon className="h-4 w-4"/>{label}</button>)}
        <p className="px-3 pb-2 pt-6 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-600">Research</p>
        {NAV.filter((x) => x.group === 'Research').map(({ id, label, icon: Icon }) => <button key={id} onClick={() => navigate(id)} className={`mb-1 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition ${section === id ? 'border border-teal-500/30 bg-teal-500/10 text-teal-200' : 'text-slate-400 hover:bg-navy-800 hover:text-white'}`}><Icon className="h-4 w-4"/>{label}</button>)}
        <p className="px-3 pb-2 pt-6 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-600">Reference</p>
        {NAV.filter((x) => x.group === 'Reference').map(({ id, label, icon: Icon }) => <button key={id} onClick={() => navigate(id)} className={`mb-1 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition ${section === id ? 'border border-teal-500/30 bg-teal-500/10 text-teal-200' : 'text-slate-400 hover:bg-navy-800 hover:text-white'}`}><Icon className="h-4 w-4"/>{label}</button>)}
        <div className="absolute bottom-4 left-3 right-3 rounded-lg border border-navy-700 bg-navy-900 p-3"><div className="text-xs font-medium text-slate-300">Research scope</div><p className="mt-1 text-[11px] leading-4 text-slate-500">BFS baseline · Static Dijkstra · Dynamic Dijkstra</p><p className="mt-2 text-[10px] text-slate-600">Ports 5174 / 8002</p></div>
      </aside>
      <main className="min-w-0 flex-1 p-4 md:p-6">
        <nav className="mb-4 flex gap-2 overflow-x-auto pb-1 lg:hidden" aria-label="Sections">{NAV.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => navigate(id)} className={`flex shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-xs ${section === id ? 'border-teal-500 bg-teal-900/40 text-teal-100' : 'border-navy-600 bg-navy-800 text-slate-400'}`}><Icon className="h-4 w-4"/>{label}</button>)}</nav>
        <div className="mx-auto max-w-[1500px]">
          {section === 'dashboard' && <ResearchDashboard onNavigate={navigate}/>}
          {section === 'network' && <Workspace module="network"/>}
          {section === 'routing' && <RoutingResilience onOpenExperiments={() => setSection('experiments')}/> }
          {section === 'packet-transfer' && <PacketTransfer/>}
          {section === 'experiments' && <ResearchLab onSaved={(id) => { setSelectedExperiment(id); setSection('results') }}/>}
          {section === 'results' && <ResearchResults selectedId={selectedExperiment}/>}
          {section === 'methodology' && <Methodology/>}
        </div>
      </main>
    </div>
  </div>
}
