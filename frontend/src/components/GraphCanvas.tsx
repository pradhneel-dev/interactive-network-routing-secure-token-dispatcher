import { useEffect, useMemo } from 'react'
import { Background, Controls, Handle, MarkerType, Position, ReactFlow, ReactFlowProvider, useNodesState, type Edge, type Node, type NodeProps } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { GraphData } from '../types'
import { edgeKey } from '../lib'

export interface NodeFlags {
  source?: boolean; target?: boolean; visited?: boolean; processed?: boolean; current?: boolean
  frontier?: boolean; route?: boolean; selected?: boolean; packets?: number[]; packetTypes?: Record<number, string>; lostHere?: boolean; failed?: boolean
}
export interface EdgeFlags {
  current?: boolean
  route?: boolean
  explored?: boolean
  selected?: boolean
  lost?: boolean
  failed?: boolean
  activePacketId?: number
  lostPacketIds?: number[]
}

interface RouterData extends Record<string, unknown> { label: string; degree: number; flags: NodeFlags }

function RouterNode({ data }: NodeProps<Node<RouterData>>) {
  const f = data.flags
  let border = 'border-navy-600', bg = 'bg-navy-700', ring = ''
  if (f.visited) { border = 'border-sky-500'; bg = 'bg-sky-950' }
  if (f.processed) { border = 'border-sky-400'; bg = 'bg-sky-900' }
  if (f.frontier) border = 'border-violet-400'
  if (f.route) { border = 'border-teal-300'; bg = 'bg-teal-900' }
  if (f.target) { border = 'border-rose-400'; bg = 'bg-rose-950' }
  if (f.source) { border = 'border-emerald-400'; bg = 'bg-emerald-950' }
  if (f.failed) { border = 'border-rose-500'; bg = 'bg-rose-950' }
  if (f.current) { border = 'border-amber-300'; ring = 'ring-2 ring-amber-300' }
  if (f.selected) ring = 'ring-2 ring-white'
  return (
    <div className={`relative min-w-[96px] rounded-lg border-2 px-3 py-1.5 text-center text-xs shadow ${border} ${bg} ${ring}`} data-testid={`node-${data.label}`}>
      <Handle type="target" position={Position.Top} style={{ top: '50%', left: '50%', opacity: 0, pointerEvents: 'none' }} />
      <Handle type="source" position={Position.Top} style={{ top: '50%', left: '50%', opacity: 0, pointerEvents: 'none' }} />
      <div className="font-semibold text-slate-100">{data.label}</div>
      <div className="text-[10px] text-slate-400">deg {data.degree}{f.source ? ' - SRC' : ''}{f.target ? ' - DST' : ''}</div>
      {f.packets && f.packets.length > 0 && (
        <div className="absolute -top-3 left-1/2 flex -translate-x-1/2 gap-0.5">
          {f.packets.map((s) => {
            const type = f.packetTypes?.[s] ?? 'data'
            const packetColor: Record<string, string> = {
              data: 'bg-cyan-300 text-navy-950', ack: 'bg-emerald-300 text-navy-950',
              control: 'bg-violet-300 text-navy-950', voice: 'bg-amber-300 text-navy-950',
              video: 'bg-rose-300 text-navy-950',
            }
            return <span key={s} className={`rounded px-1 text-[10px] font-bold ${packetColor[type] ?? packetColor.data}`}>#{s}</span>
          })}
        </div>
      )}
    </div>
  )
}
const nodeTypes = { router: RouterNode }

interface Props {
  graph: GraphData
  degrees: Record<string, number>
  nodeFlags: Record<string, NodeFlags>
  edgeFlags: Record<string, EdgeFlags>
  onSelectNode: (id: string | null) => void
  onSelectEdge: (key: string | null, u?: string, v?: string) => void
  onMoveNode: (id: string, x: number, y: number) => void
  layoutNonce?: number
}

function Inner({ graph, degrees, nodeFlags, edgeFlags, onSelectNode, onSelectEdge, onMoveNode }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<RouterData>>([])

  useEffect(() => {
    setNodes((prev) => {
      const old = new Map(prev.map((n) => [n.id, n.position]))
      return graph.nodes.map((n, i) => ({
        id: n.id, type: 'router', draggable: true,
        position: old.get(n.id) ?? { x: n.x ?? 60 + (i % 5) * 150, y: n.y ?? 60 + Math.floor(i / 5) * 110 },
        data: { label: n.id, degree: degrees[n.id] ?? 0, flags: nodeFlags[n.id] ?? {} },
      }))
    })
  }, [graph.nodes, degrees, nodeFlags, setNodes])

  // when stored positions change (layout reset / import) take them over
  useEffect(() => {
    setNodes((prev) => prev.map((n) => {
      const g = graph.nodes.find((x) => x.id === n.id)
      return g && g.x !== undefined && g.y !== undefined && (g.x !== n.position.x || g.y !== n.position.y) ? { ...n, position: { x: g.x, y: g.y } } : n
    }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph.nodes.map((n) => `${n.id}:${n.x}:${n.y}`).join('|')])

  const edges: Edge[] = useMemo(() => graph.edges.map((e) => {
    const k = edgeKey(e.u, e.v)
    const f = edgeFlags[k] ?? {}
    let stroke = '#3b4a6b', width = 2
    if (f.explored) { stroke = '#38bdf8'; width = 2.5 }
    if (f.route) { stroke = '#2dd4bf'; width = 4 }
    if (f.current) { stroke = '#fbbf24'; width = 4 }
    if (f.failed) { stroke = '#7f1d1d'; width = 4 }
    // A packet-loss fault is shown on the actual edge traversed by the packet.
    // Keep it dark red so it remains visually distinct from the active yellow edge.
    if (f.lost) { stroke = '#991b1b'; width = 4 }
    if (f.selected) { stroke = '#ffffff'; width = 4 }
    const packetLabel = f.failed
      ? 'LINK DOWN'
      : f.lost
      ? `✕ LOST${f.lostPacketIds?.length ? ` #${f.lostPacketIds.join(', #')}` : ''}`
      : f.current && f.activePacketId !== undefined
        ? `➜ PKT #${f.activePacketId}`
        : String(e.weight)
    return {
      id: k, source: e.u, target: e.v, type: 'straight',
      animated: !!f.current, style: { stroke, strokeWidth: width, strokeDasharray: f.lost || f.failed ? '6 4' : undefined },
      label: packetLabel,
      labelStyle: { fill: f.failed || f.lost ? '#fecaca' : f.current ? '#fde68a' : '#e2e8f0', fontSize: 12, fontWeight: 700 },
      labelBgStyle: { fill: f.failed || f.lost ? '#450a0a' : f.current ? '#451a03' : '#0b1220', fillOpacity: 0.98 }, labelBgPadding: [5, 3] as [number, number], labelBgBorderRadius: 4,
      markerEnd: undefined as unknown as { type: MarkerType },
      data: { u: e.u, v: e.v },
    }
  }), [graph.edges, edgeFlags])

  return (
    <ReactFlow
      nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange}
      onNodeClick={(_, n) => onSelectNode(n.id)}
      onEdgeClick={(_, e) => onSelectEdge(e.id, e.source, e.target)}
      onPaneClick={() => { onSelectNode(null); onSelectEdge(null) }}
      onNodeDragStop={(_, n) => onMoveNode(n.id, Math.round(n.position.x), Math.round(n.position.y))}
      fitView fitViewOptions={{ padding: 0.15 }} minZoom={0.2} maxZoom={2.5}
      nodesConnectable={false} proOptions={{ hideAttribution: true }} colorMode="dark"
    >
      <Background color="#1f2c47" gap={24} />
      <Controls showInteractive={false} />
    </ReactFlow>
  )
}

export default function GraphCanvas(props: Props) {
  return (
    <div className="relative h-[540px] overflow-hidden rounded-xl border border-navy-600 bg-navy-950" data-testid="graph-canvas">
      {props.graph.nodes.length === 0 && (
        <div className="absolute inset-0 z-10 flex items-center justify-center text-sm text-slate-400">Empty network. Load the demo, generate a sample, import JSON or add nodes.</div>
      )}
      <ReactFlowProvider><Inner {...props} key={props.layoutNonce ?? 0} /></ReactFlowProvider>
      <div className="pointer-events-none absolute bottom-2 right-2 z-10 rounded-md border border-navy-600 bg-navy-900/90 p-2 text-[11px] leading-5 text-slate-300">
        <Legend color="bg-emerald-400" text="Source" /><Legend color="bg-rose-400" text="Destination" />
        <Legend color="bg-sky-400" text="Visited / processed" /><Legend color="bg-violet-400" text="In queue / stack / PQ" />
        <Legend color="bg-amber-300" text="Current node / active edge" /><Legend color="bg-teal-300" text="Final route" />
        <Legend color="bg-red-700" text="Packet lost on this link" />
        <Legend color="bg-red-950" text="Link down" />
      </div>
    </div>
  )
}

function Legend({ color, text }: { color: string; text: string }) {
  return <div className="flex items-center gap-1.5"><span className={`inline-block h-2.5 w-2.5 rounded-full ${color}`} />{text}</div>
}
