import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Download, FastForward, Pause, Play, RotateCcw, SkipForward, Upload, Send, Route as RouteIcon } from 'lucide-react'
import { api, ApiError } from '../api'
import type { Algo, Analysis, Batch, DispatchResult, GraphData, RouteResult, Scenario } from '../types'
import GraphCanvas, { type EdgeFlags, type NodeFlags } from './GraphCanvas'
import { circleLayout, edgeKey, fmt, frameState, scenarioToOptions, short, traceView } from '../lib'

type Notice = { kind: 'error' | 'success' | 'info'; text: string } | null
const SPEEDS: Record<string, number> = { Slow: 1100, Normal: 600, Fast: 250, Turbo: 90 }
const SCENARIOS: { v: Scenario; label: string }[] = [
  { v: 'normal', label: 'Normal delivery' }, { v: 'drop', label: 'Drop (packet loss)' },
  { v: 'tamper_payload', label: 'Tamper payload' }, { v: 'tamper_route', label: 'Tamper route header' },
  { v: 'tamper_token', label: 'Tamper token signature' }, { v: 'duplicate', label: 'Duplicate packet' },
]
const STATUS_COLOR: Record<string, string> = {
  'Delivered & Verified': 'bg-emerald-700 text-emerald-100', 'Lost/Missing': 'bg-rose-800 text-rose-100',
  'Payload Modified': 'bg-orange-700 text-orange-100', 'Signature Invalid': 'bg-red-800 text-red-100', 'Metadata Tampered': 'bg-fuchsia-800 text-fuchsia-100',
}

export type WorkspaceModule = 'all' | 'network' | 'routing'

export default function Workspace({ module = 'all' }: { module?: WorkspaceModule }) {
  const showNetwork = module === 'all' || module === 'network'
  const showRouting = module === 'all' || module === 'routing'
  // Packet transfer now lives in its own research module. Keep the old
  // token-demo composer out of Network Studio and Routing & Resilience.
  const showLegacyPackets = false
  const [graph, setGraph] = useState<GraphData | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [connected, setConnected] = useState<boolean | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState<Notice>(null)
  const [layoutNonce, setLayoutNonce] = useState(0)

  const [source, setSource] = useState('')
  const [target, setTarget] = useState('')
  const [algo, setAlgo] = useState<Algo>('dijkstra')
  const [route, setRoute] = useState<RouteResult | null>(null)
  const [stepIdx, setStepIdx] = useState(-1)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState('Normal')

  const [selNode, setSelNode] = useState<string | null>(null)
  const [selEdge, setSelEdge] = useState<{ key: string; u: string; v: string } | null>(null)
  const [newNode, setNewNode] = useState('')
  const [edgeU, setEdgeU] = useState('')
  const [edgeV, setEdgeV] = useState('')
  const [edgeW, setEdgeW] = useState('1')
  const [edgeDelay, setEdgeDelay] = useState('1')
  const [edgeCapacity, setEdgeCapacity] = useState('10')
  const [edgeLoss, setEdgeLoss] = useState('0')
  const [edgeQueueCapacity, setEdgeQueueCapacity] = useState('20')
  const [editW, setEditW] = useState('')
  const [editDelay, setEditDelay] = useState('1')
  const [editCapacity, setEditCapacity] = useState('10')
  const [editLoss, setEditLoss] = useState('0')
  const [editQueueCapacity, setEditQueueCapacity] = useState('20')
  const fileRef = useRef<HTMLInputElement>(null)

  const [payload, setPayload] = useState('Hello from the Main Gate')
  const [count, setCount] = useState(4)
  const [batch, setBatch] = useState<Batch | null>(null)
  const [scenario, setScenario] = useState<Record<number, Scenario>>({})
  const [dropCount, setDropCount] = useState(0)
  const [dispatchRes, setDispatchRes] = useState<DispatchResult | null>(null)
  const [frame, setFrame] = useState(-1)
  const [dPlaying, setDPlaying] = useState(false)

  const fail = useCallback((e: unknown) => {
    if (e instanceof ApiError) { if (e.code === 'disconnected') setConnected(false); setNotice({ kind: 'error', text: e.message }) }
    else setNotice({ kind: 'error', text: String(e) })
  }, [])

  const applyGraph = useCallback(async (g: GraphData) => {
    setGraph(g)
    setAnalysis(await api.analysis())
    setConnected(true)
  }, [])

  const load = useCallback(async () => {
    setBusy('Connecting to backend...')
    try { await api.health(); await applyGraph(await api.getGraph()); setNotice(null) } catch (e) { setConnected(false); fail(e) } finally { setBusy(null) }
  }, [applyGraph, fail])
  useEffect(() => { void load() }, [load])

  const run = async (label: string, fn: () => Promise<GraphData>, ok?: string) => {
    setBusy(label)
    try { await applyGraph(await fn()); if (ok) setNotice({ kind: 'success', text: ok }) } catch (e) { fail(e) } finally { setBusy(null) }
  }

  const nodeIds = useMemo(() => graph?.nodes.map((n) => n.id) ?? [], [graph])
  const routeStale = !!(route && graph && route.graph_version !== graph.version)
  const batchStale = !!(batch && graph && batch.graph_version !== graph.version)

  // ----- trace player
  const total = route?.trace.length ?? 0
  useEffect(() => {
    if (!playing) return
    const t = setInterval(() => setStepIdx((i) => { if (i >= total - 1) { setPlaying(false); return i } return i + 1 }), SPEEDS[speed])
    return () => clearInterval(t)
  }, [playing, speed, total])

  const tv = useMemo(() => traceView(route?.trace ?? [], stepIdx), [route, stepIdx])
  const traceFinished = !!route && (stepIdx < 0 || stepIdx >= total - 1)

  // ----- dispatch player
  const events = dispatchRes?.events ?? []
  useEffect(() => {
    if (!dPlaying) return
    const t = setInterval(() => setFrame((i) => { if (i >= events.length - 1) { setDPlaying(false); return i } return i + 1 }), SPEEDS[speed] * 0.7)
    return () => clearInterval(t)
  }, [dPlaying, speed, events.length])
  const fs = useMemo(() => frameState(events, frame), [events, frame])
  const dispatchDone = !!dispatchRes && frame >= events.length - 1
  const dispatching = !!dispatchRes && !dispatchDone

  const degrees = analysis?.degrees ?? {}
  const nodeFlags = useMemo(() => {
    const f: Record<string, NodeFlags> = {}
    const get = (id: string) => (f[id] ??= {})
    if (source) get(source).source = true
    if (target) get(target).target = true
    tv.visited.forEach((n) => (get(n).visited = true))
    tv.processed.forEach((n) => (get(n).processed = true))
    tv.frontier.forEach((n) => (get(n).frontier = true))
    if (tv.current) get(tv.current).current = true
    if (route?.path && (traceFinished || dispatchRes)) route.path.forEach((n) => (get(n).route = true))
    if (selNode) get(selNode).selected = true
    if (dispatchRes && frame >= 0) {
      for (const [seq, pos] of Object.entries(fs.positions)) if (pos) (get(pos).packets ??= []).push(Number(seq))
      if (fs.event) get(fs.event.to ?? fs.event.from ?? '').current = true
    }
    return f
  }, [source, target, tv, route, traceFinished, dispatchRes, frame, fs, selNode])

  const edgeFlags = useMemo(() => {
    const f: Record<string, EdgeFlags> = {}
    const get = (k: string) => (f[k] ??= {})
    tv.explored.forEach((k) => (get(k).explored = true))
    if (tv.edge) get(edgeKey(tv.edge[0], tv.edge[1])).current = true
    if (route?.path && (traceFinished || dispatchRes)) route.path.slice(1).forEach((n, i) => (get(edgeKey(route.path![i], n)).route = true))
    if (fs.activeEdge) {
      const g = get(edgeKey(fs.activeEdge[0], fs.activeEdge[1]))
      if (fs.event?.kind === 'dropped') g.lost = true; else g.current = true
    }
    if (selEdge) get(selEdge.key).selected = true
    return f
  }, [tv, route, traceFinished, dispatchRes, fs, selEdge])

  // ----- actions
  const computeRoute = async () => {
    if (!source || !target) return setNotice({ kind: 'error', text: 'Choose a source and a destination first.' })
    setBusy('Computing route...')
    try {
      const r = await api.route(algo, source, target)
      setRoute(r); setStepIdx(-1); setPlaying(false); setBatch(null); setDispatchRes(null); setFrame(-1); setScenario({})
      await api.resetPackets()
      setNotice({ kind: r.found ? 'success' : 'error', text: r.message })
    } catch (e) { fail(e) } finally { setBusy(null) }
  }

  const createPackets = async () => {
    if (!route?.path) return
    setBusy('Creating packets...')
    try {
      const b = await api.createPackets({ source: route.source, destination: route.target, route: route.path, algorithm: route.algorithm, payload, count })
      setBatch(b); setDispatchRes(null); setFrame(-1); setScenario({}); setDropCount(0)
      setNotice({ kind: 'success', text: `Created ${b.packets.length} signed packet(s) in batch ${b.batch_id}.` })
    } catch (e) { fail(e) } finally { setBusy(null) }
  }

  const dispatch = async () => {
    setBusy('Dispatching...')
    try {
      const res = await api.dispatch(scenarioToOptions(scenario, dropCount))
      setDispatchRes(res); setFrame(0); setDPlaying(true)
    } catch (e) { fail(e) } finally { setBusy(null) }
  }

  const importFile = async (f: File | undefined) => {
    if (!f) return
    try { const data = JSON.parse(await f.text()); await run('Importing...', () => api.importGraph(data), 'Graph imported.'); resetFlow() } catch (e) { e instanceof SyntaxError ? setNotice({ kind: 'error', text: 'File is not valid JSON.' }) : fail(e) }
    if (fileRef.current) fileRef.current.value = ''
  }
  const exportGraph = async () => {
    try {
      const data = await api.exportGraph()
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
      Object.assign(document.createElement('a'), { href: url, download: 'irsd-graph.json' }).click()
      URL.revokeObjectURL(url)
    } catch (e) { fail(e) }
  }
  const resetFlow = () => { setRoute(null); setStepIdx(-1); setPlaying(false); setBatch(null); setDispatchRes(null); setFrame(-1); setSelNode(null); setSelEdge(null) }
  const loadDemo = async () => {
    setBusy('Loading demo...')
    try {
      const g = await api.demo(); await applyGraph(g); resetFlow()
      setSource(g.demo_pair.source); setTarget(g.demo_pair.target); setLayoutNonce((n) => n + 1)
      setNotice({ kind: 'success', text: 'Demo network loaded. Weights are simulated values.' })
    } catch (e) { fail(e) } finally { setBusy(null) }
  }
  const arrange = async () => {
    if (!graph) return
    const pos = circleLayout(graph.nodes.map((n) => n.id))
    try { await api.setPositions(pos); setGraph({ ...graph, nodes: graph.nodes.map((n) => ({ ...n, ...pos[n.id] })) }) } catch (e) { fail(e) }
  }
  const onMove = (id: string, x: number, y: number) => { void api.setPositions({ [id]: { x, y } }).catch(() => undefined) }

  const download = (name: string, data: unknown) => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
    Object.assign(document.createElement('a'), { href: url, download: name }).click(); URL.revokeObjectURL(url)
  }

  const noGraph = !graph || graph.nodes.length === 0
  const rep = dispatchRes?.report

  return (
    <div className="space-y-4">
      {connected === false && (
        <div className="flex items-center justify-between rounded-lg border border-rose-600 bg-rose-950 p-3 text-sm" role="alert">
          <span><AlertTriangle className="mr-2 inline h-4 w-4" />Disconnected: the backend is not reachable. Start it with <code className="mono">uvicorn app.main:app --port 8002</code>.</span>
          <button className="btn" onClick={() => void load()}>Retry</button>
        </div>
      )}
      {notice && (
        <div className={`rounded-lg border p-2 text-sm ${notice.kind === 'error' ? 'border-rose-600 bg-rose-950' : notice.kind === 'success' ? 'border-emerald-600 bg-emerald-950' : 'border-sky-600 bg-sky-950'}`} role="status">{notice.text}</div>
      )}
      {busy && <div className="text-xs text-teal-300">{busy}</div>}

      {/* status + toolbar */}
      <div className="panel flex flex-wrap items-center gap-3">
        <div className="flex gap-4 text-sm" data-testid="status">
          <span><b>{analysis?.node_count ?? 0}</b> nodes</span><span><b>{analysis?.edge_count ?? 0}</b> edges</span>
          <span><b>{analysis?.component_count ?? 0}</b> component(s)</span>
          <span className={analysis?.connected ? 'text-emerald-300' : 'text-amber-300'}>{analysis ? (analysis.connected ? 'Connected' : 'Not connected') : '-'}</span>
          <span className="text-slate-400">Handshake: {analysis ? (analysis.handshake.holds ? `sum deg ${analysis.handshake.degree_sum} = 2E ${analysis.handshake.twice_edges}` : 'violated') : '-'}</span>
        </div>
        {showNetwork && <div className="ml-auto flex flex-wrap gap-2">
          <button className="btn btn-primary" onClick={() => void loadDemo()}>Load demo</button>
          <button className="btn" onClick={() => void run('Generating...', () => api.sample(8), 'Sample network generated (simulated weights).').then(resetFlow)}>Generate sample</button>
          <button className="btn" onClick={() => void run('Clearing...', api.clear, 'Network cleared.').then(resetFlow)}>Clear</button>
          <button className="btn" onClick={() => void loadDemo()}>Reset to demo</button>
          <button className="btn" onClick={() => void arrange()} disabled={noGraph}>Reset layout</button>
          <button className="btn" onClick={() => fileRef.current?.click()}><Upload className="h-4 w-4" />Import JSON</button>
          <button className="btn" onClick={() => void exportGraph()} disabled={noGraph}><Download className="h-4 w-4" />Export JSON</button>
          <input ref={fileRef} type="file" accept="application/json" className="hidden" onChange={(e) => void importFile(e.target.files?.[0])} />
        </div>}
      </div>
      <p className="-mt-2 text-xs text-slate-400">Routing cost selects paths; propagation delay is stored separately and applied by the research packet simulator. Results are simulated, not physical network measurements.</p>

      <div className={`grid gap-4 lg:grid-cols-12 ${showRouting && showNetwork ? '' : ''}`}>
        <div className={showRouting ? 'lg:col-span-8' : 'lg:col-span-12'}>
          {graph ? (
            <GraphCanvas graph={graph} degrees={degrees} nodeFlags={nodeFlags} edgeFlags={edgeFlags} layoutNonce={layoutNonce}
              onSelectNode={(id) => { setSelNode(id); if (id) setSelEdge(null) }}
              onSelectEdge={(key, u, v) => { setSelEdge(key && u && v ? { key, u, v } : null); if (key) setSelNode(null); const w = graph.edges.find((e) => key === edgeKey(e.u, e.v)); setEditW(w ? String(w.weight) : ''); setEditDelay(w ? String(w.propagation_delay_ms ?? 1) : '1'); setEditCapacity(w ? String(w.capacity_mbps ?? 10) : '10'); setEditLoss(w ? String(w.loss_probability ?? 0) : '0'); setEditQueueCapacity(w ? String(w.queue_capacity_packets ?? 20) : '20') }}
              onMoveNode={onMove} />
          ) : <div className="panel flex h-[540px] items-center justify-center text-slate-400">{busy ?? 'No graph loaded.'}</div>}
        </div>

        {showRouting && <div className="space-y-4 lg:col-span-4">
          <section className="panel">
            <h2>1. Route</h2>
            <div className="grid grid-cols-2 gap-2">
              <div><label className="label" htmlFor="src">Source</label>
                <select id="src" className="input w-full" value={source} onChange={(e) => setSource(e.target.value)}><option value="">-</option>{nodeIds.map((n) => <option key={n}>{n}</option>)}</select></div>
              <div><label className="label" htmlFor="dst">Destination</label>
                <select id="dst" className="input w-full" value={target} onChange={(e) => setTarget(e.target.value)}><option value="">-</option>{nodeIds.map((n) => <option key={n}>{n}</option>)}</select></div>
            </div>
            <label className="label mt-2" htmlFor="algo">Algorithm</label>
            <select id="algo" className="input w-full" value={algo} onChange={(e) => setAlgo(e.target.value as Algo)}>
              <option value="bfs">BFS - minimum hops (ignores weights)</option><option value="dfs">DFS - any path found (not shortest)</option><option value="dijkstra">Dijkstra - minimum total cost</option>
            </select>
            <button className="btn btn-primary mt-3 w-full justify-center" onClick={() => void computeRoute()} disabled={noGraph || !!busy}><RouteIcon className="h-4 w-4" />Compute route</button>
            {route && (
              <div className="mt-3 rounded-lg border border-navy-600 bg-navy-900 p-3 text-sm" data-testid="route-result">
                {routeStale && <div className="mb-2 rounded bg-amber-900 p-2 text-xs text-amber-100" role="alert">Graph changed after this route was computed - route is STALE. Recompute.</div>}
                {route.found ? (<>
                  <div className="mono text-teal-200">{route.path!.join(' -> ')}</div>
                  <div className="mt-1 text-xs text-slate-300">{route.label}</div>
                  <div className="mt-2 flex gap-4"><span>Hops: <b data-testid="route-hops">{route.hops}</b></span><span>Total cost: <b data-testid="route-cost">{fmt(route.cost)}</b></span></div>
                  {route.algorithm === 'bfs' && <div className="mt-1 text-xs text-slate-400">BFS minimises hops, so its cost may be higher than Dijkstra's.</div>}
                </>) : <div className="text-rose-300">{route.message}</div>}
              </div>
            )}
          </section>

          <section className="panel">
            <h2>2. Algorithm trace</h2>
            {!route ? <p className="text-sm text-slate-400">Compute a route to see the real step-by-step trace.</p> : (<>
              <div className="flex flex-wrap gap-1.5">
                <button className="btn" onClick={() => { if (stepIdx >= total - 1) setStepIdx(0); setPlaying(true) }} disabled={playing}><Play className="h-4 w-4" />Play</button>
                <button className="btn" onClick={() => setPlaying(false)} disabled={!playing}><Pause className="h-4 w-4" />Pause</button>
                <button className="btn" onClick={() => { setPlaying(false); setStepIdx((i) => Math.min(i + 1, total - 1)) }}><SkipForward className="h-4 w-4" />Next</button>
                <button className="btn" onClick={() => { setPlaying(false); setStepIdx(-1) }}><RotateCcw className="h-4 w-4" />Reset</button>
                <button className="btn" onClick={() => { setStepIdx(0); setPlaying(true) }}>Replay</button>
                <select aria-label="Speed" className="input" value={speed} onChange={(e) => setSpeed(e.target.value)}>{Object.keys(SPEEDS).map((s) => <option key={s}>{s}</option>)}</select>
              </div>
              <div className="mt-2 text-xs text-slate-400">Step {Math.max(stepIdx + 1, 0)} / {total}</div>
              <div className="mt-1 min-h-[2.5rem] rounded bg-navy-900 p-2 text-xs" data-testid="trace-message">{tv.step?.message ?? 'Press Play or Next.'}</div>
              {tv.step && (
                <div className="mt-2 space-y-1 text-xs">
                  <div><span className="text-slate-400">{tv.step.frontier_type === 'queue' ? 'Queue' : tv.step.frontier_type === 'stack' ? 'Stack' : 'Priority queue'}:</span> <span className="mono">[{tv.frontierLabels.join(', ')}]</span></div>
                  <div><span className="text-slate-400">Visited:</span> {tv.step.visited.length} / {nodeIds.length}</div>
                  {tv.step.distances && (
                    <table className="mt-1 w-full text-left"><thead><tr className="text-slate-400"><th>Node</th><th>Dist</th><th>Pred</th></tr></thead><tbody>
                      {Object.entries(tv.step.distances).map(([n, d]) => <tr key={n} className={tv.step!.processed.includes(n) ? 'text-sky-300' : ''}><td>{n}</td><td>{d === null ? 'inf' : d}</td><td>{tv.step!.predecessors?.[n] ?? '-'}</td></tr>)}
                    </tbody></table>
                  )}
                </div>
              )}
            </>)}
          </section>
        </div>}
      </div>

      {showNetwork && <div className="grid gap-4 lg:grid-cols-3">
        {/* editor */}
        <section className="panel">
          <h2>Network editor</h2>
          <div className="flex gap-2"><input className="input flex-1" placeholder="New node id" value={newNode} onChange={(e) => setNewNode(e.target.value)} aria-label="New node id" />
            <button className="btn" onClick={() => void run('Adding node...', () => api.addNode(newNode, 200 + Math.random() * 300, 150 + Math.random() * 200), `Node '${newNode.trim()}' added.`).then(() => setNewNode(''))}>Add node</button></div>
          <div className="mt-3 grid grid-cols-3 gap-2">
            <select className="input" aria-label="Edge from" value={edgeU} onChange={(e) => setEdgeU(e.target.value)}><option value="">from</option>{nodeIds.map((n) => <option key={n}>{n}</option>)}</select>
            <select className="input" aria-label="Edge to" value={edgeV} onChange={(e) => setEdgeV(e.target.value)}><option value="">to</option>{nodeIds.map((n) => <option key={n}>{n}</option>)}</select>
            <input className="input" type="number" min="0" aria-label="Routing cost" value={edgeW} onChange={(e) => setEdgeW(e.target.value)} />
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <div><label className="label" htmlFor="new-delay">Propagation delay (ms)</label><input id="new-delay" className="input w-full" type="number" min="0" value={edgeDelay} onChange={(e) => setEdgeDelay(e.target.value)} /></div>
            <div><label className="label" htmlFor="new-capacity">Capacity (Mbps)</label><input id="new-capacity" className="input w-full" type="number" min="0.001" value={edgeCapacity} onChange={(e) => setEdgeCapacity(e.target.value)} /></div>
            <div><label className="label" htmlFor="new-loss">Loss probability</label><input id="new-loss" className="input w-full" type="number" min="0" max="1" step="0.01" value={edgeLoss} onChange={(e) => setEdgeLoss(e.target.value)} /></div>
            <div><label className="label" htmlFor="new-queue">Queue capacity (packets)</label><input id="new-queue" className="input w-full" type="number" min="1" value={edgeQueueCapacity} onChange={(e) => setEdgeQueueCapacity(e.target.value)} /></div>
          </div>
          <button className="btn mt-2" onClick={() => void run('Adding edge...', () => api.addEdge(edgeU, edgeV, Number(edgeW), { propagation_delay_ms: Number(edgeDelay), capacity_mbps: Number(edgeCapacity), loss_probability: Number(edgeLoss), queue_capacity_packets: Number(edgeQueueCapacity) }), 'Edge added. Routing cost and propagation delay are stored separately.')}>Add edge</button>
          <div className="mt-3 border-t border-navy-600 pt-3 text-sm">
            {selNode && (<div className="space-y-2"><div>Selected node: <b>{selNode}</b> (degree {degrees[selNode] ?? 0})</div>
              <div className="flex flex-wrap gap-2"><button className="btn" onClick={() => setSource(selNode)}>Set as source</button><button className="btn" onClick={() => setTarget(selNode)}>Set as destination</button>
                <button className="btn btn-danger" onClick={() => void run('Removing...', () => api.deleteNode(selNode), `Node '${selNode}' removed.`).then(() => setSelNode(null))}>Remove node</button></div></div>)}
            {selEdge && (<div className="space-y-2"><div>Selected edge: <b>{selEdge.u} - {selEdge.v}</b></div>
              <div className="grid grid-cols-2 gap-2">
                <div><label className="label" htmlFor="edit-cost">Routing cost</label><input id="edit-cost" className="input w-full" type="number" min="0" value={editW} onChange={(e) => setEditW(e.target.value)} /></div>
                <div><label className="label" htmlFor="edit-delay">Propagation delay (ms)</label><input id="edit-delay" className="input w-full" type="number" min="0" value={editDelay} onChange={(e) => setEditDelay(e.target.value)} /></div>
                <div><label className="label" htmlFor="edit-capacity">Capacity (Mbps)</label><input id="edit-capacity" className="input w-full" type="number" min="0.001" value={editCapacity} onChange={(e) => setEditCapacity(e.target.value)} /></div>
                <div><label className="label" htmlFor="edit-loss">Loss probability (0-1)</label><input id="edit-loss" className="input w-full" type="number" min="0" max="1" step="0.01" value={editLoss} onChange={(e) => setEditLoss(e.target.value)} /></div>
                <div><label className="label" htmlFor="edit-queue">Queue capacity (packets)</label><input id="edit-queue" className="input w-full" type="number" min="1" value={editQueueCapacity} onChange={(e) => setEditQueueCapacity(e.target.value)} /></div>
              </div>
              <div className="mt-2 flex gap-2"><button className="btn" onClick={() => void run('Updating...', () => api.updateEdge(selEdge.u, selEdge.v, Number(editW), { propagation_delay_ms: Number(editDelay), capacity_mbps: Number(editCapacity), loss_probability: Number(editLoss), queue_capacity_packets: Number(editQueueCapacity) }), 'Routing cost and link simulation properties updated independently.')}>Update link properties</button>
                <button className="btn btn-danger" onClick={() => void run('Removing...', () => api.deleteEdge(selEdge.u, selEdge.v), 'Edge removed.').then(() => setSelEdge(null))}>Remove edge</button></div></div>)}
            {!selNode && !selEdge && <p className="text-xs text-slate-400">Click a node or edge on the canvas to select, edit or remove it. Drag nodes to move them.</p>}
          </div>
        </section>

        {/* legacy packet composer retained for backward compatibility; research authentication uses Ed25519 */}
        {showLegacyPackets && <section className="panel">
          <h2>3. Packets &amp; dispatch</h2>
          <div className="mb-2 rounded border border-amber-700 bg-amber-950 p-2 text-xs text-amber-200">Academic/toy cryptography - not production security.</div>
          <label className="label" htmlFor="payload">Payload</label>
          <input id="payload" className="input w-full" value={payload} onChange={(e) => setPayload(e.target.value)} />
          <div className="mt-2 flex items-end gap-2"><div><label className="label" htmlFor="cnt">Packets (1-20)</label>
            <input id="cnt" className="input w-20" type="number" min={1} max={20} value={count} onChange={(e) => setCount(Number(e.target.value))} /></div>
            <button className="btn btn-primary" onClick={() => void createPackets()} disabled={!route?.found || routeStale || !!busy}><Send className="h-4 w-4" />Create packets</button></div>
          {!route?.found && <p className="mt-2 text-xs text-slate-400">Compute a route first; dispatch uses exactly that route.</p>}
          {batch && (<div className="mt-3 text-xs">
            {batchStale && <div className="mb-2 rounded bg-amber-900 p-2 text-amber-100" role="alert">Graph changed: these packets are stale. Recompute the route and recreate them.</div>}
            <div className="mb-1 text-slate-400">Batch {batch.batch_id}: {batch.route.join(' -> ')}</div>
            <table className="w-full text-left"><thead className="text-slate-400"><tr><th>#</th><th>Packet ID</th><th>Fault scenario</th></tr></thead><tbody>
              {batch.packets.map((p) => (<tr key={p.packet_id}><td>{p.seq}</td>
                <td title={`digest ${p.token.payload_digest}`}>{p.packet_id}</td>
                <td><select aria-label={`Scenario for packet ${p.seq}`} className="input w-full py-0.5 text-xs" value={scenario[p.seq] ?? 'normal'} disabled={dispatching}
                  onChange={(e) => setScenario((s) => ({ ...s, [p.seq]: e.target.value as Scenario }))}>{SCENARIOS.map((s) => <option key={s.v} value={s.v}>{s.label}</option>)}</select></td></tr>))}
            </tbody></table>
            <div className="mt-2 flex items-center gap-2"><label className="text-slate-400" htmlFor="dc">Also drop the last N packets</label>
              <input id="dc" className="input w-16 py-0.5" type="number" min={0} max={batch.packets.length} value={dropCount} onChange={(e) => setDropCount(Number(e.target.value))} /></div>
            <button className="btn btn-primary mt-3" onClick={() => void dispatch()} disabled={batchStale || !!busy || dispatching}><Send className="h-4 w-4" />Dispatch</button>
          </div>)}
        </section>}
      </div>}

      {showLegacyPackets && <div className="grid gap-4 lg:grid-cols-2">
        {/* animation log */}
        <section className="panel">
          <h2>Dispatch animation &amp; log</h2>
          {!dispatchRes ? <p className="text-sm text-slate-400">Create and dispatch packets to watch them move hop by hop along the computed route.</p> : (<>
            <div className="flex flex-wrap gap-1.5">
              <button className="btn" onClick={() => { if (frame >= events.length - 1) setFrame(0); setDPlaying(true) }} disabled={dPlaying}><Play className="h-4 w-4" />Play</button>
              <button className="btn" onClick={() => setDPlaying(false)} disabled={!dPlaying}><Pause className="h-4 w-4" />Pause</button>
              <button className="btn" onClick={() => { setDPlaying(false); setFrame((i) => Math.min(i + 1, events.length - 1)) }}><SkipForward className="h-4 w-4" />Step</button>
              <button className="btn" onClick={() => { setFrame(0); setDPlaying(true) }}>Replay</button>
              <button className="btn" onClick={() => { setDPlaying(false); setFrame(events.length - 1) }}><FastForward className="h-4 w-4" />Skip</button>
              <button className="btn" onClick={() => { setDPlaying(false); setDispatchRes(null); setFrame(-1) }}><RotateCcw className="h-4 w-4" />Reset</button>
            </div>
            {fs.event && (<div className="mt-2 rounded bg-navy-900 p-2 text-xs" data-testid="current-event">
              <div>Packet <b>{fs.event.packet_id}</b> - status <b>{fs.event.status}</b></div>
              <div>Router: <b>{fs.event.to ?? fs.event.from}</b>{fs.event.hop !== null && <> - hop counter <b>{fs.event.hop}</b>/{route?.hops}</>}</div>
            </div>)}
            <ol className="mt-2 max-h-64 space-y-0.5 overflow-auto text-xs" data-testid="event-log">
              {fs.visibleEvents.map((e) => <li key={e.index} className={e.kind === 'dropped' ? 'text-rose-300' : e.kind === 'tamper' ? 'text-orange-300' : e.kind === 'arrived' ? 'text-emerald-300' : e.kind === 'duplicate' ? 'text-fuchsia-300' : 'text-slate-300'}>{e.index + 1}. {e.message}</li>)}
            </ol></>)}
        </section>
      </div>}

      {/* legacy token-dispatch receiver/report stays out of the research modules */}
      {showLegacyPackets && <div className="grid gap-4 lg:grid-cols-2">
        <section className="panel" data-testid="receiver">
          <h2>4. Destination receiver &amp; verification</h2>
          {!dispatchRes ? <p className="text-sm text-slate-400">Waiting for a dispatch.</p> : !dispatchDone ? <p className="text-sm text-slate-400">Packets still in transit... (use Skip to jump to the end)</p> : (<>
            <div className="mb-2 text-xs text-slate-400">Step A - packet loss: expected IDs vs received IDs. Step B - for each received packet: nonce decryption, signature, metadata and payload digest checks.</div>
            <table className="w-full text-left text-xs"><thead className="text-slate-400"><tr><th>Packet</th><th>Arrived?</th><th>Result</th><th>Checks</th></tr></thead><tbody>
              {dispatchRes.results.map((r) => (<tr key={r.packet_id} className="border-t border-navy-600 align-top">
                <td className="py-1">{r.packet_id}</td><td>{r.received ? 'yes' : <b className="text-rose-300">MISSING</b>}</td>
                <td><span className={`badge ${STATUS_COLOR[r.status] ?? 'bg-slate-700'}`}>{r.status}</span></td>
                <td>{r.checks ? (<ul>
                  <li>nonce recovered: {short(String(r.checks.nonce_recovered))}</li>
                  <li>signature: {r.checks.signature_valid ? 'valid' : <b className="text-rose-300">INVALID</b>}</li>
                  <li>metadata signature: {r.checks.metadata_signature_valid ? 'valid' : <b className="text-rose-300">INVALID</b>}</li>
                  <li>payload digest: {r.checks.digest_matches ? 'match' : <b className="text-rose-300">MISMATCH</b>}</li></ul>) : <span className="text-slate-400">no payload to check</span>}
                  <div className="mt-1 text-slate-400">{r.explanation}</div></td></tr>))}
            </tbody></table></>)}
        </section>

        <section className="panel" data-testid="report">
          <h2>5. Transmission report</h2>
          {!rep || !dispatchDone ? <p className="text-sm text-slate-400">The report is calculated from the real simulation once packets have been delivered.</p> : (<>
            <div className="mb-2 text-xs text-slate-300">{rep.algorithm_label}</div>
            <div className="mono mb-2 text-xs text-teal-200">{rep.route.join(' -> ')}</div>
            <div className="grid grid-cols-3 gap-2 text-center text-sm">
              {([['Hops', rep.hops], ['Cost', fmt(rep.cost)], ['Sent', rep.packets_sent], ['Received', rep.packets_received], ['Lost', rep.packets_lost], ['Verified', rep.delivered_verified],
                ['Integrity fails', rep.integrity_failures], ['Signature fails', rep.signature_failures], ['Metadata fails', rep.metadata_failures]] as [string, string | number][]).map(([k, v]) => (
                <div key={k} className="rounded bg-navy-900 p-2"><div className="text-[11px] text-slate-400">{k}</div><div className="text-lg font-bold" data-testid={`rep-${k}`}>{v}</div></div>))}
            </div>
            <div className="mt-3 flex items-center gap-2 text-lg">{rep.delivery_percentage === 100 ? <CheckCircle2 className="h-5 w-5 text-emerald-400" /> : <AlertTriangle className="h-5 w-5 text-amber-400" />}
              Delivery: <b data-testid="rep-pct">{rep.delivery_percentage}%</b> <span className="text-xs text-slate-400">(verified / sent)</span></div>
            {rep.lost_ids.length > 0 && <div className="mt-1 text-xs text-rose-300">Missing IDs: {rep.lost_ids.join(', ')}</div>}
            {rep.duplicates_ignored > 0 && <div className="mt-1 text-xs text-fuchsia-300">Duplicate copies ignored: {rep.duplicates_ignored}</div>}
            <button className="btn mt-3" onClick={() => download(`irsd-report-${rep.batch_id}.json`, rep)}><Download className="h-4 w-4" />Download report JSON</button>
          </>)}
        </section>
      </div>}
    </div>
  )
}
