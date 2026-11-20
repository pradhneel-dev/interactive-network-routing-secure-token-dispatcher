import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity, CheckCircle2, Download, FastForward, Pause,
  Play, RotateCcw, Send, StepForward, Zap,
} from 'lucide-react'
import { api, ApiError } from '../api'
import type {
  Analysis, GraphData, PacketClass, PacketProfileInput, PacketScenario,
  PacketTraceEvent, PacketTransferResult,
} from '../types'
import GraphCanvas, { type EdgeFlags, type NodeFlags } from './GraphCanvas'
import { edgeKey } from '../lib'

const CLASSES: { type: PacketClass; label: string; size: number; description: string; accent: string }[] = [
  { type: 'data', label: 'DATA', size: 512, description: 'General application payload', accent: 'text-cyan-300' },
  { type: 'ack', label: 'ACK', size: 64, description: 'Small acknowledgement traffic', accent: 'text-emerald-300' },
  { type: 'control', label: 'CONTROL', size: 128, description: 'Network control messages', accent: 'text-violet-300' },
  { type: 'voice', label: 'VOICE', size: 160, description: 'Low-size real-time traffic profile', accent: 'text-amber-300' },
  { type: 'video', label: 'VIDEO', size: 1400, description: 'Larger media traffic profile', accent: 'text-rose-300' },
]
const SPEED_MS: Record<string, number> = { Slow: 1000, Normal: 550, Fast: 220, Turbo: 80 }
const DEFAULT_COUNTS: Record<PacketClass, number> = { data: 3, ack: 1, control: 1, voice: 0, video: 0 }
const DEFAULT_SIZES: Record<PacketClass, number> = { data: 512, ack: 64, control: 128, voice: 160, video: 1400 }

type FailureKind = 'none' | 'link' | 'node'

function saveJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(href)
}

function humanStatus(status: string) {
  const labels: Record<string, string> = {
    delivered: 'Delivered', delivered_payload_modified: 'Delivered · payload altered',
    delivered_route_header_modified: 'Delivered · route metadata altered',
    dropped_simulated: 'Lost on route edge (test scenario)', dropped_link_failure: 'Link failure',
    dropped_node_failure: 'Node failure', dropped_link_loss: 'Link loss', dropped_queue_overflow: 'Queue overflow',
    dropped_no_route: 'No route', expired_packets: 'TTL expired', security_rejected_packets: 'Security rejected',
  }
  return labels[status] ?? status.replaceAll('_', ' ')
}

function statusClass(status: string) {
  if (status === 'delivered') return 'bg-emerald-900 text-emerald-200'
  if (status === 'delivered_payload_modified' || status === 'delivered_route_header_modified') return 'bg-amber-900 text-amber-200'
  if (status === 'dropped_simulated' || status.startsWith('dropped') || status === 'expired_packets') return 'bg-rose-950 text-rose-200'
  return 'bg-slate-700 text-slate-200'
}

export default function PacketTransfer() {
  const [graph, setGraph] = useState<GraphData | null>(null)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [source, setSource] = useState('')
  const [destination, setDestination] = useState('')
  const [algorithm, setAlgorithm] = useState<'bfs' | 'dijkstra_static' | 'dijkstra_dynamic'>('dijkstra_dynamic')
  const [basePayload, setBasePayload] = useState('IRSD sample message')
  const [counts, setCounts] = useState<Record<PacketClass, number>>(DEFAULT_COUNTS)
  const [sizes, setSizes] = useState<Record<PacketClass, number>>(DEFAULT_SIZES)
  const [profiles, setProfiles] = useState<PacketProfileInput[]>([])
  const [durationMs, setDurationMs] = useState(2500)
  const [trafficModel, setTrafficModel] = useState<'constant' | 'variable' | 'burst'>('constant')
  const [ttl, setTtl] = useState(24)
  const [seed, setSeed] = useState(2026)
  const [failureKind, setFailureKind] = useState<FailureKind>('none')
  const [failureResource, setFailureResource] = useState('')
  const [failureAtMs, setFailureAtMs] = useState(450)
  const [failureDurationMs, setFailureDurationMs] = useState(700)
  const [result, setResult] = useState<PacketTransferResult | null>(null)
  const [frame, setFrame] = useState(-1)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState('Normal')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadGraph = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [g, a] = await Promise.all([api.getGraph(), api.analysis()])
      setGraph(g)
      setAnalysis(a)
      setSource((old) => old && g.nodes.some((n) => n.id === old) ? old : g.nodes[0]?.id ?? '')
      setDestination((old) => old && g.nodes.some((n) => n.id === old) ? old : g.nodes[g.nodes.length - 1]?.id ?? '')
      setFailureResource((old) => {
        const validLink = old.includes('::') && g.edges.some((edge) => `${edge.u}::${edge.v}` === old)
        const validNode = g.nodes.some((node) => node.id === old)
        if (old && (validLink || validNode)) return old
        const firstEdge = g.edges[0]
        if (firstEdge) return `${firstEdge.u}::${firstEdge.v}`
        return g.nodes[1]?.id ?? ''
      })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void loadGraph() }, [loadGraph])
  useEffect(() => {
    if (!playing || !result) return
    const timer = window.setInterval(() => {
      setFrame((current) => {
        if (current >= result.trace_events.length - 1) {
          setPlaying(false)
          return current
        }
        return current + 1
      })
    }, SPEED_MS[speed])
    return () => window.clearInterval(timer)
  }, [playing, result, speed])

  const nodes = graph?.nodes ?? []
  const totalPackets = CLASSES.reduce((sum, c) => sum + counts[c.type], 0)
  const currentEvent = result && frame >= 0 ? result.trace_events[frame] ?? null : null
  const complete = !!result && frame >= result.trace_events.length - 1

  const createBatch = () => {
    if (!graph || !source || !destination || source === destination) {
      setError('Select different source and destination nodes first.')
      return
    }
    if (totalPackets < 1 || totalPackets > 100) {
      setError('Create between 1 and 100 packets.')
      return
    }
    if (!basePayload.trim()) {
      setError('Enter a payload template before creating packets.')
      return
    }
    const next: PacketProfileInput[] = []
    for (const definition of CLASSES) {
      for (let i = 0; i < counts[definition.type]; i += 1) {
        const id = next.length + 1
        next.push({
          packet_type: definition.type,
          size_bytes: sizes[definition.type],
          payload: `${basePayload.trim()} · ${definition.label} packet ${id}`,
          scenario: 'normal',
        })
      }
    }
    setProfiles(next)
    setResult(null)
    setFrame(-1)
    setPlaying(false)
    setError(null)
  }

  const updateScenario = (index: number, scenario: PacketScenario) => {
    setProfiles((current) => current.map((profile, i) => i === index ? { ...profile, scenario } : profile))
  }

  const runTransfer = async () => {
    if (!graph || profiles.length === 0) {
      setError('Create a packet batch before starting the transfer.')
      return
    }
    if (failureKind !== 'none' && failureAtMs > durationMs) {
      setError('Failure time must fall within the configured traffic duration.')
      return
    }
    if (failureKind === 'link' && !graph.edges.some((edge) => `${edge.u}::${edge.v}` === failureResource)) {
      setError('Choose an existing link for the failure injection.')
      return
    }
    if (failureKind === 'node' && !graph.nodes.some((node) => node.id === failureResource)) {
      setError('Choose an existing node for the failure injection.')
      return
    }
    const failures = failureKind === 'none' ? [] : failureKind === 'link'
      ? [{ kind: 'link' as const, at_ms: failureAtMs, duration_ms: failureDurationMs,
          u: failureResource.split('::')[0], v: failureResource.split('::')[1] }]
      : [{ kind: 'node' as const, at_ms: failureAtMs, duration_ms: failureDurationMs, node: failureResource }]
    setLoading(true)
    setError(null)
    setPlaying(false)
    try {
      const transfer = await api.packetTransfer({
        source, destination, algorithm, packet_profiles: profiles,
        duration_ms: durationMs, traffic_model: trafficModel, ttl, seed, failures,
      })
      setResult(transfer)
      setFrame(transfer.trace_events.length ? 0 : -1)
      setPlaying(transfer.trace_events.length > 0)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const visualState = useMemo(() => {
    const nodeFlags: Record<string, NodeFlags> = {}
    const edgeFlags: Record<string, EdgeFlags> = {}
    const ensureNode = (id: string) => (nodeFlags[id] ??= {})
    const packetPositions = new Map<number, string>()
    const failedLinks = new Set<string>()
    const failedNodes = new Set<string>()
    const traversedEdges = new Set<string>()
    const lostPacketsByEdge = new Map<string, number[]>()
    let activeEdge: [string, string] | null = null
    let activeNode: string | null = null
    let activePacketId: number | undefined
    const events = result?.trace_events.slice(0, Math.max(0, frame + 1)) ?? []
    for (const event of events) {
      if (event.kind === 'link_down' && event.from_node && event.to_node) failedLinks.add(edgeKey(event.from_node, event.to_node))
      if (event.kind === 'link_up' && event.from_node && event.to_node) failedLinks.delete(edgeKey(event.from_node, event.to_node))
      if (event.kind === 'node_down' && event.from_node) failedNodes.add(event.from_node)
      if (event.kind === 'node_up' && event.from_node) failedNodes.delete(event.from_node)
      if (event.packet_id !== null) {
        if (event.kind === 'generated') packetPositions.set(event.packet_id, event.from_node ?? source)
        else if (event.kind === 'hop_arrival' || event.kind === 'delivered' || event.kind === 'duplicate') packetPositions.set(event.packet_id, event.to_node ?? destination)
        else if (event.kind === 'transmitting' || event.kind === 'serialization_complete') packetPositions.delete(event.packet_id)
        else if (event.kind === 'packet_lost_on_link' && event.from_node && event.to_node) {
          const key = edgeKey(event.from_node, event.to_node)
          lostPacketsByEdge.set(key, [...(lostPacketsByEdge.get(key) ?? []), event.packet_id])
          packetPositions.delete(event.packet_id)
        }
        else if (event.kind === 'dropped') packetPositions.set(event.packet_id, event.from_node ?? event.to_node ?? source)
        else if (event.from_node) packetPositions.set(event.packet_id, event.from_node)
      }
      if (event.kind === 'transmitting' && event.from_node && event.to_node) {
        activeEdge = [event.from_node, event.to_node]
        activeNode = event.from_node
        activePacketId = event.packet_id ?? undefined
      } else if (event.kind === 'hop_arrival') {
        if (event.from_node && event.to_node) traversedEdges.add(edgeKey(event.from_node, event.to_node))
        activeEdge = null
        activeNode = event.to_node
        activePacketId = undefined
      } else if (event.kind === 'packet_lost_on_link') {
        activeEdge = null
        activeNode = null
        activePacketId = undefined
      } else if (event.kind === 'delivered' || event.kind === 'dropped') {
        activeEdge = null
        activeNode = event.to_node ?? event.from_node
        activePacketId = undefined
      }
    }
    if (source) ensureNode(source).source = true
    if (destination) ensureNode(destination).target = true
    for (const [packetId, nodeId] of packetPositions) {
      if (!nodeId || !graph?.nodes.some((node) => node.id === nodeId)) continue
      const flags = ensureNode(nodeId)
      ;(flags.packets ??= []).push(packetId)
      const type = result?.packets.find((packet) => packet.packet_id === packetId)?.packet_type ?? 'data'
      ;(flags.packetTypes ??= {})[packetId] = type
    }
    if (activeNode) ensureNode(activeNode).current = true
    for (const nodeId of failedNodes) ensureNode(nodeId).failed = true
    // Highlight only hops already present in the replayed event prefix. Do not
    // reveal a packet's final route before the animation reaches those hops.
    for (const key of traversedEdges) edgeFlags[key] = { ...(edgeFlags[key] ?? {}), route: true }
    for (const key of failedLinks) edgeFlags[key] = { ...(edgeFlags[key] ?? {}), failed: true }
    for (const [key, packetIds] of lostPacketsByEdge) {
      edgeFlags[key] = { ...(edgeFlags[key] ?? {}), lost: true, lostPacketIds: packetIds }
    }
    if (activeEdge) {
      const key = edgeKey(activeEdge[0], activeEdge[1])
      edgeFlags[key] = { ...(edgeFlags[key] ?? {}), current: true, activePacketId }
    }
    return { nodeFlags, edgeFlags, activeEdge, packetPositions }
  }, [result, frame, source, destination, graph])

  const currentVisibleEvents = result?.trace_events.slice(0, frame + 1) ?? []
  const metrics = result?.metrics ?? {}
  const readMetric = (key: string, digits = 2) => {
    const value = metrics[key]
    if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
    return value.toFixed(digits)
  }

  return <div className="space-y-5">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p className="text-xs uppercase tracking-[0.22em] text-teal-300">Interactive packet simulation</p>
        <h2 className="mt-1 text-2xl font-semibold text-white">Packet Transfer</h2>
        <p className="mt-1 max-w-3xl text-sm text-slate-400">Create mixed traffic, send packets through the current topology and replay their hop-by-hop movement. Packet classes use different simulated payload sizes.</p>
      </div>
      <div className="flex items-center gap-2">
        <span className="badge bg-slate-700 text-slate-200">Local simulation only</span>
        <button className="btn" onClick={() => void loadGraph()} disabled={loading}><RotateCcw className="h-4 w-4"/>Refresh graph</button>
      </div>
    </div>

    {error && <div className="rounded-lg border border-rose-700 bg-rose-950/70 p-3 text-sm text-rose-200" role="alert">{error}</div>}

    <div className="grid gap-4 xl:grid-cols-12">
      <section className="panel space-y-4 xl:col-span-4">
        <div className="flex items-center gap-2"><Send className="h-5 w-5 text-teal-300"/><h3 className="text-sm font-semibold text-white">1. Configure transfer</h3></div>
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs text-slate-400">Source node
            <select className="input mt-1 w-full" value={source} onChange={(e) => setSource(e.target.value)}>{nodes.map((n) => <option key={n.id} value={n.id}>{n.id}</option>)}</select>
          </label>
          <label className="text-xs text-slate-400">Destination node
            <select className="input mt-1 w-full" value={destination} onChange={(e) => setDestination(e.target.value)}>{nodes.map((n) => <option key={n.id} value={n.id}>{n.id}</option>)}</select>
          </label>
        </div>
        <label className="block text-xs text-slate-400">Routing algorithm
          <select className="input mt-1 w-full" value={algorithm} onChange={(e) => setAlgorithm(e.target.value as typeof algorithm)}>
            <option value="bfs">BFS — minimum hops</option>
            <option value="dijkstra_static">Static Dijkstra — frozen route</option>
            <option value="dijkstra_dynamic">Dynamic Dijkstra — adaptive route</option>
          </select>
        </label>
        <label className="block text-xs text-slate-400">Payload template
          <input className="input mt-1 w-full" value={basePayload} maxLength={450} onChange={(e) => setBasePayload(e.target.value)} placeholder="Enter the message carried by each packet"/>
          <span className="mt-1 block text-[10px] text-slate-500">Each generated packet gets a unique ID and class suffix.</span>
        </label>
        <div>
          <div className="mb-2 flex items-center justify-between"><h4 className="text-xs font-semibold text-slate-200">2. Packet mix</h4><span className="text-xs text-slate-500">{totalPackets}/100 packets</span></div>
          <div className="space-y-2">
            {CLASSES.map((item) => <div key={item.type} className="grid grid-cols-[1fr_72px_92px] items-center gap-2 rounded-lg border border-navy-700 bg-navy-900/70 p-2">
              <div><div className={`text-xs font-semibold ${item.accent}`}>{item.label}</div><div className="text-[10px] text-slate-500">{item.description}</div></div>
              <label className="text-[10px] text-slate-500">Count<input className="input mt-1 w-full px-2 py-1" type="number" min={0} max={100} value={counts[item.type]} onChange={(e) => setCounts((old) => ({ ...old, [item.type]: Math.max(0, Math.min(100, Number(e.target.value) || 0)) }))}/></label>
              <label className="text-[10px] text-slate-500">Size (bytes)<input className="input mt-1 w-full px-2 py-1" type="number" min={1} max={65535} value={sizes[item.type]} onChange={(e) => setSizes((old) => ({ ...old, [item.type]: Math.max(1, Math.min(65535, Number(e.target.value) || 1)) }))}/></label>
            </div>)}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs text-slate-400">Traffic pattern<select className="input mt-1 w-full" value={trafficModel} onChange={(e) => setTrafficModel(e.target.value as typeof trafficModel)}><option value="constant">Constant rate</option><option value="variable">Variable arrivals</option><option value="burst">Burst traffic</option></select></label>
          <label className="text-xs text-slate-400">TTL (hops)<input className="input mt-1 w-full" type="number" min={1} max={255} value={ttl} onChange={(e) => setTtl(Math.max(1, Math.min(255, Number(e.target.value) || 1)))}/></label>
          <label className="text-xs text-slate-400">Traffic duration (ms)<input className="input mt-1 w-full" type="number" min={10} max={60000} value={durationMs} onChange={(e) => setDurationMs(Math.max(10, Math.min(60000, Number(e.target.value) || 10)))}/></label>
          <label className="text-xs text-slate-400">Random seed<input className="input mt-1 w-full" type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value) || 0)}/></label>
        </div>
        <div className="rounded-lg border border-navy-700 bg-navy-900/60 p-3">
          <label className="flex items-center gap-2 text-xs font-semibold text-slate-200"><input type="checkbox" checked={failureKind !== 'none'} onChange={(e) => setFailureKind(e.target.checked ? 'link' : 'none')}/> Inject a temporary network failure</label>
          {failureKind !== 'none' && <div className="mt-3 space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <label className="text-[10px] text-slate-500">Failure type<select className="input mt-1 w-full" value={failureKind} onChange={(e) => { const next = e.target.value as FailureKind; setFailureKind(next); setFailureResource(next === 'link' ? (graph?.edges[0] ? `${graph.edges[0].u}::${graph.edges[0].v}` : '') : graph?.nodes[1]?.id ?? '') }}><option value="link">Link failure</option><option value="node">Node failure</option></select></label>
              <label className="text-[10px] text-slate-500">Target {failureKind === 'link' ? 'link' : 'node'}
                <select className="input mt-1 w-full" value={failureResource} onChange={(e) => setFailureResource(e.target.value)}>
                  {failureKind === 'link' ? graph?.edges.map((edge) => <option key={`${edge.u}::${edge.v}`} value={`${edge.u}::${edge.v}`}>{edge.u} ↔ {edge.v}</option>) : graph?.nodes.map((node) => <option key={node.id} value={node.id}>{node.id}</option>)}
                </select>
              </label>
            </div>
            <div className="grid grid-cols-2 gap-2"><label className="text-[10px] text-slate-500">Failure at (ms)<input className="input mt-1 w-full" type="number" min={0} value={failureAtMs} onChange={(e) => setFailureAtMs(Math.max(0, Number(e.target.value) || 0))}/></label><label className="text-[10px] text-slate-500">Duration (ms)<input className="input mt-1 w-full" type="number" min={1} value={failureDurationMs} onChange={(e) => setFailureDurationMs(Math.max(1, Number(e.target.value) || 1))}/></label></div>
            <p className="text-[10px] leading-4 text-slate-500">Use Static Dijkstra and Dynamic Dijkstra with the same failure to observe the difference between a frozen route and adaptive rerouting.</p>
          </div>}
        </div>
        <button className="btn btn-primary w-full justify-center" onClick={createBatch} disabled={!graph || totalPackets < 1 || totalPackets > 100 || source === destination || loading}>Create {totalPackets} packet(s)</button>
      </section>

      <section className="panel xl:col-span-8">
        <div className="flex flex-wrap items-center justify-between gap-2"><div><h3 className="text-sm font-semibold text-white">3. Packet batch</h3><p className="mt-1 text-xs text-slate-400">Assign each packet a transfer behaviour before dispatch.</p></div>{profiles.length > 0 && <button className="btn btn-primary" onClick={() => void runTransfer()} disabled={loading}>{loading ? 'Simulating…' : 'Start packet transfer'} <Send className="h-4 w-4"/></button>}</div>
        {profiles.length === 0 ? <div className="mt-4 flex min-h-56 flex-col items-center justify-center rounded-lg border border-dashed border-navy-600 text-center"><Zap className="h-8 w-8 text-slate-600"/><p className="mt-3 text-sm text-slate-300">No packets created yet</p><p className="mt-1 max-w-sm text-xs text-slate-500">Choose a source, destination and packet mix, then create a batch to configure individual packet scenarios.</p></div> : <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[620px] text-left text-xs"><thead className="border-b border-navy-600 text-slate-500"><tr><th className="py-2">Packet ID</th><th>Type</th><th>Payload size</th><th>Payload preview</th><th>Scenario</th></tr></thead><tbody>{profiles.map((profile, index) => <tr key={`${profile.packet_type}-${index}`} className="border-b border-navy-800"><td className="py-2 font-mono text-slate-300">PKT-{String(index + 1).padStart(3, '0')}</td><td className="font-semibold text-slate-200">{profile.packet_type.toUpperCase()}</td><td>{profile.size_bytes} B</td><td className="max-w-40 truncate text-slate-500">{profile.payload}</td><td><select className="input py-1 text-xs" value={profile.scenario} onChange={(e) => updateScenario(index, e.target.value as PacketScenario)}><option value="normal">Normal delivery</option><option value="drop">Lose on a route edge</option><option value="tamper_payload">Modify payload in transit</option><option value="tamper_route">Alter route metadata</option><option value="duplicate">Duplicate at destination</option></select></td></tr>)}</tbody></table></div>}
        {profiles.some((profile) => profile.scenario === 'drop') && <p className="mt-2 text-xs text-rose-300">Packet-loss scenario: this packet is not skipped. It is queued and transmitted over the route, completes serialization on a selected intermediate edge, then is lost before reaching the next node. The loss location is shown in dark red during replay.</p>}
      </section>
    </div>

    <section className="panel space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="text-sm font-semibold text-white">4. Live network transfer</h3><p className="mt-1 text-xs text-slate-400">Replay the discrete-event trace on the current topology.</p></div>{result && <span className="badge bg-slate-700 text-slate-200">Transfer {result.transfer_id}</span>}</div>
      {!graph || loading && !result ? <div className="flex h-[480px] items-center justify-center text-sm text-slate-500">{loading ? 'Loading topology…' : 'No topology available.'}</div> : <div className="grid gap-4 xl:grid-cols-12">
        <div className="xl:col-span-8"><GraphCanvas graph={graph} degrees={analysis?.degrees ?? {}} nodeFlags={visualState.nodeFlags} edgeFlags={visualState.edgeFlags} onSelectNode={() => undefined} onSelectEdge={() => undefined} onMoveNode={() => undefined}/></div>
        <div className="space-y-3 xl:col-span-4">
          <div className="rounded-lg border border-navy-700 bg-navy-900 p-3"><div className="text-xs font-semibold text-slate-300">Transfer event</div>{currentEvent ? <><div className="mt-2 text-sm font-medium text-white">{humanStatus(currentEvent.status ?? currentEvent.kind)}</div><p className="mt-1 text-xs leading-5 text-slate-400">{currentEvent.message}</p><div className="mt-2 flex flex-wrap gap-2 text-[10px] text-slate-500"><span>{currentEvent.at_ms.toFixed(3)} ms</span>{currentEvent.packet_id !== null && <span>Packet #{currentEvent.packet_id}</span>}{currentEvent.hop !== null && <span>Hop {currentEvent.hop}</span>}</div></> : <p className="mt-2 text-xs text-slate-500">Create and run a transfer to inspect packet movement.</p>}</div>
          <div className="rounded-lg border border-navy-700 bg-navy-900 p-3"><div className="flex items-center justify-between text-xs"><span className="font-semibold text-slate-300">Playback</span><span className="text-slate-500">{result ? `${Math.max(0, frame + 1)} / ${result.trace_events.length}` : '—'}</span></div><div className="mt-2 flex flex-wrap gap-1.5"><button className="btn" onClick={() => { if (result) { if (complete) setFrame(0); setPlaying(true) } }} disabled={!result || playing}><Play className="h-3.5 w-3.5"/>Play</button><button className="btn" onClick={() => setPlaying(false)} disabled={!playing}><Pause className="h-3.5 w-3.5"/>Pause</button><button className="btn" onClick={() => { setPlaying(false); setFrame((i) => Math.min(i + 1, (result?.trace_events.length ?? 1) - 1)) }} disabled={!result || complete}><StepForward className="h-3.5 w-3.5"/>Step</button><button className="btn" onClick={() => { if (result) { setFrame(0); setPlaying(true) } }} disabled={!result}><RotateCcw className="h-3.5 w-3.5"/>Replay</button><button className="btn" onClick={() => { setPlaying(false); setFrame((result?.trace_events.length ?? 1) - 1) }} disabled={!result}><FastForward className="h-3.5 w-3.5"/>Skip</button></div><div className="mt-3 flex items-center gap-2"><span className="text-[10px] text-slate-500">Speed</span><select className="input py-1 text-xs" value={speed} onChange={(e) => setSpeed(e.target.value)}>{Object.keys(SPEED_MS).map((value) => <option key={value}>{value}</option>)}</select></div><div className="mt-3 h-1.5 overflow-hidden rounded-full bg-navy-700"><div className="h-full rounded-full bg-teal-400 transition-all" style={{ width: `${result?.trace_events.length ? Math.max(0, (frame + 1) / result.trace_events.length * 100) : 0}%` }}/></div></div>
          <div className="rounded-lg border border-navy-700 bg-navy-900 p-3"><div className="mb-2 text-xs font-semibold text-slate-300">Packet legend</div><div className="grid grid-cols-2 gap-2 text-[10px] text-slate-400">{CLASSES.map((c) => <div key={c.type} className="flex items-center gap-2"><span className={`h-2.5 w-2.5 rounded-full ${c.type === 'data' ? 'bg-cyan-400' : c.type === 'ack' ? 'bg-emerald-400' : c.type === 'control' ? 'bg-violet-400' : c.type === 'voice' ? 'bg-amber-400' : 'bg-rose-400'}`}/>{c.label} · {c.size} B default</div>)}</div></div>
        </div>
      </div>}
      {result?.trace_truncated && <p className="text-xs text-amber-300">The event trace reached its safety limit; only the first 12,000 events are available for playback.</p>}
      {result && <div className="flex flex-wrap items-center justify-between gap-2 border-t border-navy-700 pt-3"><p className="text-xs text-slate-500">{complete ? 'Simulation trace completed.' : 'The simulation result is ready; use playback to inspect packet movement.'} · {currentVisibleEvents.length} events shown</p><button className="btn" onClick={() => saveJson(`irsd-packet-transfer-${result.transfer_id}.json`, result)}><Download className="h-4 w-4"/>Export transfer JSON</button></div>}
    </section>

    {result && <>
      <section className="space-y-3">
        <div><p className="text-xs uppercase tracking-[0.2em] text-teal-300">Transmission report</p><h3 className="mt-1 text-lg font-semibold text-white">Transfer results</h3></div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ['Packets sent', result.metrics.generated_packets], ['Delivered', result.metrics.network_delivered_packets],
            ['Dropped / expired', Number(result.metrics.dropped_link_failure ?? 0) + Number(result.metrics.dropped_node_failure ?? 0) + Number(result.metrics.dropped_link_loss ?? 0) + Number(result.metrics.dropped_queue_overflow ?? 0) + Number(result.metrics.dropped_no_route ?? 0) + Number(result.metrics.dropped_simulated ?? 0) + Number(result.metrics.expired_packets ?? 0)],
            ['Delivery ratio', `${(Number(result.metrics.packet_delivery_ratio ?? 0) * 100).toFixed(1)}%`],
            ['Mean latency', `${readMetric('mean_latency_ms', 3)} ms`], ['P95 latency', `${readMetric('p95_latency_ms', 3)} ms`],
            ['Throughput', `${readMetric('throughput_mbps', 6)} Mbps`], ['Hop attempts', result.metrics.hops_attempted_total ?? 0],
            ['Bytes serialized', result.metrics.transmitted_bytes ?? 0], ['Duplicate copies', result.metrics.duplicate_copies ?? 0],
            ['Payload altered', result.metrics.payload_tampered_packets ?? 0], ['Route metadata altered', result.metrics.route_header_tampered_packets ?? 0],
          ].map(([label, value]) => <div key={String(label)} className="panel"><div className="text-xs text-slate-400">{label}</div><div className="mt-2 text-2xl font-semibold text-white">{value ?? '—'}</div></div>)}
        </div>
        <div className="panel overflow-x-auto"><div className="mb-3 flex flex-wrap items-center justify-between gap-2"><h4 className="text-sm font-semibold text-white">Individual packet outcomes</h4><span className="text-xs text-slate-500">{result.packets.length} packets</span></div><table className="w-full min-w-[900px] text-left text-xs"><thead className="border-b border-navy-600 text-slate-500"><tr><th className="py-2">ID</th><th>Type</th><th>Size</th><th>Scenario</th><th>Status</th><th>Hops</th><th>Lost edge</th><th>Latency</th><th>Route history</th><th>Duplicates</th></tr></thead><tbody>{result.packets.map((packet) => <tr key={packet.packet_id} className="border-b border-navy-800 align-top"><td className="py-2 font-mono">PKT-{String(packet.packet_id).padStart(3, '0')}</td><td>{packet.packet_type.toUpperCase()}</td><td>{packet.size_bytes} B</td><td>{packet.scenario.replaceAll('_', ' ')}</td><td><span className={`badge ${statusClass(packet.status)}`}>{humanStatus(packet.status)}</span><div className="mt-1 max-w-52 text-[10px] text-slate-500">{packet.reason}</div></td><td>{packet.hops}<span className="block text-[10px] text-slate-500">{packet.attempted_hops ?? packet.hops} attempted</span></td><td className="text-rose-300">{packet.lost_on_edge ? `${packet.lost_on_edge.from_node} → ${packet.lost_on_edge.to_node}` : '—'}</td><td>{packet.latency_ms === null ? '—' : `${packet.latency_ms.toFixed(3)} ms`}</td><td className="max-w-64 text-slate-400">{packet.route_history.join(' → ') || '—'}</td><td>{packet.duplicate_copies}</td></tr>)}</tbody></table></div>
      </section>
      <section className="panel"><div className="mb-2 flex items-center gap-2"><Activity className="h-4 w-4 text-teal-300"/><h4 className="text-sm font-semibold text-white">Simulation event log</h4></div><ol className="max-h-72 space-y-1 overflow-auto text-xs">{currentVisibleEvents.slice(-120).map((event: PacketTraceEvent) => <li key={event.index} className="flex gap-3 border-b border-navy-800 py-1.5"><span className="w-20 shrink-0 font-mono text-slate-500">{event.at_ms.toFixed(2)} ms</span><span className={`w-28 shrink-0 ${event.kind === 'packet_lost_on_link' || event.kind === 'dropped' ? 'text-rose-300' : event.kind.includes('tampered') ? 'text-amber-300' : 'text-teal-300'}`}>{event.kind.replaceAll('_', ' ')}</span><span className="text-slate-300">{event.message}</span></li>)}</ol><div className="mt-2 flex items-center gap-2 text-[10px] text-slate-500"><CheckCircle2 className="h-3.5 w-3.5"/>Simulation events are generated by the backend discrete-event engine; no real network traffic is transmitted.</div></section>
    </>}
  </div>
}
