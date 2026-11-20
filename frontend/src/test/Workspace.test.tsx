import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Batch, DispatchResult, GraphData, RouteResult } from '../types'

vi.mock('../components/GraphCanvas', () => ({
  default: (p: { graph: GraphData; nodeFlags: Record<string, { route?: boolean }>; edgeFlags: Record<string, { route?: boolean }> }) => (
    <div data-testid="canvas" data-nodes={p.graph.nodes.length} data-route-nodes={Object.entries(p.nodeFlags).filter(([, f]) => f.route).map(([k]) => k).sort().join(',')} data-route-edges={Object.values(p.edgeFlags).filter((f) => f.route).length} />
  ),
}))
vi.mock('../api', async (orig) => {
  const real = await orig<typeof import('../api')>()
  const fns = ['health', 'getGraph', 'analysis', 'route', 'resetPackets', 'createPackets', 'dispatch', 'addEdge', 'demo'] as const
  return { ...real, api: Object.fromEntries(fns.map((f) => [f, vi.fn()])) }
})
import { api, ApiError } from '../api'
import Workspace from '../components/Workspace'

const graph: GraphData = { nodes: ['A', 'B', 'C'].map((id) => ({ id })), edges: [{ u: 'A', v: 'B', weight: 2 }, { u: 'B', v: 'C', weight: 3 }], version: 1, weights_simulated: true, note: '' }
const analysis = { node_count: 3, edge_count: 2, degrees: { A: 1, B: 2, C: 1 }, handshake: { degree_sum: 4, twice_edges: 4, holds: true }, components: [['A', 'B', 'C']], component_count: 1, connected: true, isolated_nodes: [], euler: { classification: 'trail', odd_vertices: ['A', 'C'], reason: '' }, adjacency_list: {}, adjacency_matrix: { labels: [], matrix: [], note: '' }, version: 1 }
const route: RouteResult = { algorithm: 'dijkstra', source: 'A', target: 'C', found: true, path: ['A', 'B', 'C'], hops: 2, cost: 5, label: 'Minimum-cost path', traversal_order: ['A', 'B', 'C'], message: 'ok', graph_version: 1,
  trace: [{ index: 0, kind: 'init', message: 'Distance(A) = 0', current: 'A', edge: null, visited: ['A'], processed: [], frontier: [['A', 0]], frontier_type: 'priority_queue', distances: { A: 0, B: null, C: null }, predecessors: { A: null } }] }
const batch: Batch = { batch_id: 'ABC123', source: 'A', destination: 'C', route: ['A', 'B', 'C'], algorithm: 'dijkstra', hops: 2, cost: 5, graph_version: 1, expected_ids: ['P1', 'P2'], warning: '',
  packets: [1, 2].map((s) => ({ packet_id: `P${s}`, seq: s, source: 'A', destination: 'C', route: ['A', 'B', 'C'], payload: 'hi', status: 'Created', token: { token_id: `T${s}`, packet_id: `P${s}`, seq: s, source: 'A', destination: 'C', route: ['A', 'B', 'C'], payload_digest: 'd', encrypted_nonce: 1, signature: 2 } })) }
const dres: DispatchResult = {
  events: [
    { index: 0, kind: 'send', packet_id: 'P1', seq: 1, from: 'A', to: 'A', hop: 0, status: 'Sent', message: 'P1 created at A' },
    { index: 1, kind: 'dropped', packet_id: 'P2', seq: 2, from: 'A', to: 'B', hop: 1, status: 'Lost', message: 'P2 was lost on link A -> B' }],
  results: [{ packet_id: 'P1', seq: 1, received: true, verified: true, status: 'Delivered & Verified', checks: { nonce_recovered: 5, signature_valid: true, metadata_signature_valid: true, digest_matches: true }, reasons: [], explanation: 'ok', duplicate_copies: 0 },
    { packet_id: 'P2', seq: 2, received: false, verified: false, status: 'Lost/Missing', checks: null, reasons: [], explanation: 'never arrived', duplicate_copies: 0 }],
  report: { batch_id: 'ABC123', algorithm: 'dijkstra', algorithm_label: 'Minimum-cost path', route: ['A', 'B', 'C'], hops: 2, cost: 5, packets_sent: 2, packets_received: 1, packets_lost: 1, lost_ids: ['P2'], delivered_verified: 1, integrity_failures: 0, signature_failures: 0, metadata_failures: 0, duplicates_ignored: 0, delivery_percentage: 50, per_packet: [] },
  options_applied: {} }

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.health).mockResolvedValue({ status: 'ok', port: 8002 })
  vi.mocked(api.getGraph).mockResolvedValue(graph)
  vi.mocked(api.analysis).mockResolvedValue(analysis as never)
  vi.mocked(api.route).mockResolvedValue(route)
  vi.mocked(api.resetPackets).mockResolvedValue({ ok: true })
  vi.mocked(api.createPackets).mockResolvedValue(batch)
  vi.mocked(api.dispatch).mockResolvedValue(dres)
})

describe('Workspace', () => {
  it('shows a disconnected state when the backend is down', async () => {
    vi.mocked(api.health).mockRejectedValue(new ApiError('Cannot reach the backend', 'disconnected', 0))
    render(<Workspace />)
    expect(await screen.findByText(/Disconnected/)).toBeInTheDocument()
  })

  it('loads the graph, computes a route, highlights it and shows hops/cost', async () => {
    const user = userEvent.setup()
    render(<Workspace />)
    await waitFor(() => expect(screen.getByTestId('canvas')).toHaveAttribute('data-nodes', '3'))
    expect(screen.getByTestId('status')).toHaveTextContent('3 nodes')
    await user.selectOptions(screen.getByLabelText('Source'), 'A')
    await user.selectOptions(screen.getByLabelText('Destination'), 'C')
    await user.click(screen.getByRole('button', { name: /Compute route/ }))
    expect(api.route).toHaveBeenCalledWith('dijkstra', 'A', 'C')
    expect(await screen.findByTestId('route-cost')).toHaveTextContent('5')
    expect(screen.getByTestId('route-hops')).toHaveTextContent('2')
    expect(screen.getByTestId('canvas')).toHaveAttribute('data-route-nodes', 'A,B,C')
    expect(screen.getByTestId('canvas')).toHaveAttribute('data-route-edges', '2')
  })

  it('steps through the real trace', async () => {
    const user = userEvent.setup()
    render(<Workspace />)
    await waitFor(() => expect(screen.getByTestId('canvas')).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText('Source'), 'A'); await user.selectOptions(screen.getByLabelText('Destination'), 'C')
    await user.click(screen.getByRole('button', { name: /Compute route/ }))
    await screen.findByTestId('route-result')
    await user.click(screen.getByRole('button', { name: /Next/ }))
    expect(screen.getByTestId('trace-message')).toHaveTextContent('Distance(A) = 0')
  })

  it('dispatch with a drop produces a report that matches the simulation', async () => {
    const user = userEvent.setup()
    render(<Workspace />)
    await waitFor(() => expect(screen.getByTestId('canvas')).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText('Source'), 'A'); await user.selectOptions(screen.getByLabelText('Destination'), 'C')
    await user.click(screen.getByRole('button', { name: /Compute route/ }))
    await screen.findByTestId('route-result')
    await user.click(screen.getByRole('button', { name: /Create packets/ }))
    await user.selectOptions(await screen.findByLabelText('Scenario for packet 2'), 'drop')
    await user.click(screen.getByRole('button', { name: /^Dispatch$/ }))
    expect(api.dispatch).toHaveBeenCalledWith(expect.objectContaining({ drop_seqs: [2], tamper_payload_seqs: [] }))
    await user.click(await screen.findByRole('button', { name: /Skip/ }))
    const report = await screen.findByTestId('report')
    expect(within(report).getByTestId('rep-Lost')).toHaveTextContent('1')
    expect(within(report).getByTestId('rep-Received')).toHaveTextContent('1')
    expect(within(report).getByTestId('rep-pct')).toHaveTextContent('50%')
    const rcv = screen.getByTestId('receiver')
    expect(within(rcv).getByText('MISSING')).toBeInTheDocument()
    expect(within(rcv).getByText('Lost/Missing')).toBeInTheDocument()
  })

  it('surfaces API errors from graph editing', async () => {
    vi.mocked(api.addEdge).mockRejectedValue(new ApiError('Negative edge weights are rejected', 'negative_weight', 400))
    const user = userEvent.setup()
    render(<Workspace />)
    await waitFor(() => expect(screen.getByTestId('canvas')).toBeInTheDocument())
    await user.selectOptions(screen.getByLabelText('Edge from'), 'A'); await user.selectOptions(screen.getByLabelText('Edge to'), 'C')
    await user.click(screen.getByRole('button', { name: 'Add edge' }))
    expect(await screen.findByText(/Negative edge weights are rejected/)).toBeInTheDocument()
  })
})
