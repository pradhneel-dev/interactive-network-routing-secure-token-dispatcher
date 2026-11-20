export type Algo = 'bfs' | 'dfs' | 'dijkstra'

export interface GNode { id: string; x?: number; y?: number; status?: 'up' | 'down' }
export interface GEdge { u: string; v: string; weight: number; propagation_delay_ms?: number; capacity_mbps?: number; loss_probability?: number; queue_capacity_packets?: number; status?: 'up' | 'down' }
export interface GraphData { nodes: GNode[]; edges: GEdge[]; version: number; weights_simulated: boolean; note: string }

export type PacketClass = 'data' | 'ack' | 'control' | 'voice' | 'video'
export type PacketScenario = 'normal' | 'drop' | 'duplicate' | 'tamper_payload' | 'tamper_route'
export interface PacketProfileInput {
  packet_type: PacketClass
  size_bytes: number
  payload: string
  scenario: PacketScenario
}
export interface FailureSchedule {
  kind: 'link' | 'node'
  at_ms: number
  duration_ms: number
  u?: string
  v?: string
  node?: string
}
export interface PacketTransferRequest {
  source: string
  destination: string
  algorithm: 'bfs' | 'dijkstra_static' | 'dijkstra_dynamic'
  packet_profiles: PacketProfileInput[]
  duration_ms: number
  traffic_model: 'constant' | 'variable' | 'burst'
  ttl: number
  seed: number
  failures: FailureSchedule[]
}
export interface PacketTraceEvent {
  index: number
  at_ms: number
  kind: string
  packet_id: number | null
  packet_type: PacketClass | null
  from_node: string | null
  to_node: string | null
  hop: number | null
  status: string | null
  message: string
}
export interface TransferredPacket {
  packet_id: number
  packet_type: PacketClass
  size_bytes: number
  status: string
  reason: string
  scenario: PacketScenario
  payload_modified: boolean
  route_header_modified: boolean
  generated_at_ms: number
  finished_at_ms: number | null
  latency_ms: number | null
  hops: number
  attempted_hops?: number
  route_history: string[]
  edge_attempts?: { from_node: string; to_node: string; started_at_ms: number; status: string; hop: number; serialized_at_ms?: number; lost_at_ms?: number }[]
  lost_on_edge?: { from_node: string; to_node: string; hop: number; lost_at_ms: number } | null
  duplicate_copies: number
}
export interface PacketTransferResult {
  transfer_id: string
  graph_version: number
  source: string
  destination: string
  algorithm: PacketTransferRequest['algorithm']
  traffic_model: PacketTransferRequest['traffic_model']
  packet_count: number
  metrics: Record<string, number | boolean | null>
  packets: TransferredPacket[]
  trace_events: PacketTraceEvent[]
  trace_truncated: boolean
  note: string
}

export interface TraceStep {
  index: number
  kind: string
  message: string
  current: string | null
  edge: [string, string] | null
  visited: string[]
  processed: string[]
  frontier: (string | [string, number])[]
  frontier_type: 'queue' | 'stack' | 'priority_queue'
  distances?: Record<string, number | null>
  predecessors?: Record<string, string | null>
  improved?: boolean
  discovered_new?: boolean
}

export interface RouteResult {
  algorithm: Algo
  source: string
  target: string
  found: boolean
  path: string[] | null
  hops: number | null
  cost: number | null
  label: string
  trace: TraceStep[]
  traversal_order: string[]
  message: string
  graph_version: number
}

export interface Analysis {
  node_count: number
  edge_count: number
  degrees: Record<string, number>
  handshake: { degree_sum: number; twice_edges: number; holds: boolean }
  components: string[][]
  component_count: number
  connected: boolean
  isolated_nodes: string[]
  euler: { classification: 'circuit' | 'trail' | 'none'; odd_vertices: string[]; reason: string }
  adjacency_list: Record<string, { node: string; weight: number }[]>
  adjacency_matrix: { labels: string[]; matrix: number[][]; note: string }
  operational?: {
    active_node_count: number; active_edge_count: number; failed_nodes: string[];
    failed_edges: [string, string][]; unavailable_edges: [string, string][];
    degrees: Record<string, number>; components: string[][]; component_count: number;
    connected: boolean; isolated_nodes: string[]
  }
  version: number
}

export interface Token {
  token_id: string; packet_id: string; seq: number; source: string; destination: string
  route: string[]; payload_digest: string; encrypted_nonce: number; signature: number
}
export interface PacketT {
  packet_id: string; seq: number; source: string; destination: string
  route: string[]; payload: string; token: Token; status: string
}
export interface Batch {
  batch_id: string; source: string; destination: string; route: string[]; algorithm: Algo
  hops: number; cost: number; graph_version: number; expected_ids: string[]; packets: PacketT[]; warning: string
}

export interface DispatchEvent {
  index: number; kind: 'send' | 'hop' | 'dropped' | 'tamper' | 'arrived' | 'duplicate'
  packet_id: string; seq: number; from: string | null; to: string | null; hop: number | null
  status: string; message: string; final_status?: string
}
export interface PacketResult {
  packet_id: string; seq: number; received: boolean; verified: boolean; status: string
  checks: { nonce_recovered: number | null; signature_valid: boolean; metadata_signature_valid: boolean; digest_matches: boolean } | null
  reasons: string[]; explanation: string; duplicate_copies: number
}
export interface Report {
  batch_id: string; algorithm: Algo; algorithm_label: string; route: string[]; hops: number; cost: number
  packets_sent: number; packets_received: number; packets_lost: number; lost_ids: string[]
  delivered_verified: number; integrity_failures: number; signature_failures: number; metadata_failures: number
  duplicates_ignored: number; delivery_percentage: number; per_packet: PacketResult[]
}
export interface DispatchResult {
  events: DispatchEvent[]; results: PacketResult[]; report: Report
  options_applied: Record<string, number[]>
}

export type Scenario = 'normal' | 'drop' | 'tamper_payload' | 'tamper_route' | 'tamper_token' | 'duplicate'
export interface DispatchBody {
  drop_seqs: number[]; drop_count: number; tamper_payload_seqs: number[]
  tamper_route_seqs: number[]; tamper_token_seqs: number[]; duplicate_seqs: number[]
}
