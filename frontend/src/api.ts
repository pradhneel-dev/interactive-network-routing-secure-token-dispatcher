import type { Algo, Analysis, Batch, DispatchBody, DispatchResult, FailureSchedule, GraphData, PacketTransferRequest, PacketTransferResult, Report, RouteResult } from './types'

/** Backend base URL. Read from VITE_API_URL (see .env.example); default matches the documented port 8002. */
export const API_URL: string = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://127.0.0.1:8002'

export class ApiError extends Error {
  code: string
  status: number
  constructor(message: string, code: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

export async function request<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: init?.method ?? 'GET',
      headers: init?.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
    })
  } catch {
    throw new ApiError(`Cannot reach the backend at ${API_URL}. Is it running?`, 'disconnected', 0)
  }
  let data: unknown = null
  try { data = await res.json() } catch { /* empty body */ }
  if (!res.ok) {
    const d = data as { error?: { code: string; message: string }; detail?: unknown } | null
    if (d?.error) throw new ApiError(d.error.message, d.error.code, res.status)
    const detail = Array.isArray(d?.detail) ? (d?.detail as { msg: string }[]).map((x) => x.msg).join('; ') : String(d?.detail ?? res.statusText)
    throw new ApiError(detail, 'validation_error', res.status)
  }
  return data as T
}

const post = <T,>(path: string, body: unknown = {}) => request<T>(path, { method: 'POST', body })

export const api = {
  health: () => request<{ status: string; port: number }>('/health'),
  getGraph: () => request<GraphData>('/graph'),
  analysis: () => request<Analysis>('/graph/analysis'),
  exportGraph: () => request<Record<string, unknown>>('/graph/export'),
  importGraph: (data: unknown) => request<GraphData>('/graph', { method: 'PUT', body: data }),
  demo: () => post<GraphData & { demo_pair: { source: string; target: string } }>('/graph/demo'),
  sample: (nodes: number) => post<GraphData>('/graph/sample', { nodes }),
  clear: () => post<GraphData>('/graph/clear'),
  addNode: (id: string, x?: number, y?: number) => post<GraphData>('/graph/nodes', { id, x, y }),
  deleteNode: (id: string) => request<GraphData>(`/graph/nodes/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  addEdge: (u: string, v: string, weight: number, properties?: { propagation_delay_ms?: number; capacity_mbps?: number; loss_probability?: number; queue_capacity_packets?: number }) => post<GraphData>('/graph/edges', { u, v, weight, ...properties }),
  updateEdge: (u: string, v: string, weight: number, properties?: { propagation_delay_ms?: number; capacity_mbps?: number; loss_probability?: number; queue_capacity_packets?: number; status?: 'up' | 'down' }) => request<GraphData>('/graph/edges', { method: 'PUT', body: { u, v, weight, ...properties } }),
  deleteEdge: (u: string, v: string) => request<GraphData>(`/graph/edges?u=${encodeURIComponent(u)}&v=${encodeURIComponent(v)}`, { method: 'DELETE' }),
  setPositions: (positions: Record<string, { x: number; y: number }>) => request<{ ok: boolean }>('/graph/positions', { method: 'PUT', body: { positions } }),
  route: (algo: Algo, source: string, target: string) => post<RouteResult>(`/routing/${algo}`, { source, target }),
  hamiltonian: (kind: 'path' | 'cycle') => request<{ kind: string; exists: boolean; sequence: string[] | null; reason: string }>(`/graph/hamiltonian?kind=${kind}`),
  coloring: () => request<{ colors: Record<string, number>; num_colors: number; valid: boolean; note: string }>('/graph/coloring'),
  traverse: (algo: 'bfs' | 'dfs', source: string) => post<{ traversal_order: string[] }>(`/graph/traverse/${algo}`, { source }),
  createPackets: (b: { source: string; destination: string; route: string[]; algorithm: Algo; payload: string; count: number }) => post<Batch>('/packets/create', b),
  dispatch: (b: DispatchBody) => post<DispatchResult>('/packets/dispatch', b),
  report: () => request<Report>('/packets/report'),
  resetPackets: () => post<{ ok: boolean }>('/packets/reset'),
  packetTransfer: (body: PacketTransferRequest) => post<PacketTransferResult>('/packets/transfer', body),
  runExperiment: (body: ExperimentRequest) => post<ExperimentResult>('/experiments/run', body),
  experiments: () => request<{ experiments: ExperimentIndex[] }>('/experiments'),
  experiment: (id: string) => request<ExperimentDetail>(`/experiments/${encodeURIComponent(id)}`),
  packetOutcomes: (runId: string, offset = 0, limit = 100) => request<PacketOutcomePage>(`/experiments/runs/${encodeURIComponent(runId)}/packets?offset=${offset}&limit=${limit}`),
  // number theory / tokens
  gcd: (a: number, b: number) => post<{ gcd: number; steps: { a: number; b: number; q: number; r: number }[] }>('/numtheory/gcd', { a, b }),
  egcd: (a: number, b: number) => post<{ gcd: number; x: number; y: number; identity: string; verified: boolean; table: { q: number; r: number; s: number; t: number }[] }>('/numtheory/egcd', { a, b }),
  modinv: (a: number, m: number) => post<{ inverse: number; check: string }>('/numtheory/modinv', { a, m }),
  modexp: (base: number, exp: number, mod: number) => post<{ result: number }>('/numtheory/modexp', { base, exp, mod }),
  keys: (body: { bits?: number; p?: number; q?: number; e?: number }) => post<{ p: number; q: number; n: number; phi: number; public: { n: number; e: number }; private: { n: number; d: number }; steps: string[]; warning: string }>('/rsa/keys', body),
  encrypt: (value: number, n: number, key: number) => post<{ ciphertext: number }>('/rsa/encrypt', { value, n, key }),
  decrypt: (value: number, n: number, key: number) => post<{ plaintext: number }>('/rsa/decrypt', { value, n, key }),
  tokenCreate: (source: string, destination: string, payload: string) => post<{ token: Record<string, unknown>; payload: string; warning: string }>('/tokens/create', { source, destination, payload }),
  tokenVerify: (token: Record<string, unknown>, payload: string, packet_header: Record<string, unknown>) => post<{ valid: boolean; status: string; checks: Record<string, unknown>; reasons: string[] }>('/tokens/verify', { token, payload, packet_header }),
  // math lab
  additive: (initial: number, increment: number, steps: number) => post<MathSeq>('/math/additive', { initial, increment, steps }),
  backoff: (initial_delay: number, factor: number, steps: number, cap: number | null) => post<MathSeq>('/math/backoff', { initial_delay, factor, steps, cap }),
  fibonacci: (n: number, f0: number, f1: number) => post<MathSeq>('/math/fibonacci', { n, f0, f1 }),
  walks: (degree: number, steps: number) => post<MathSeq>('/math/walks', { degree, steps }),
  walksExact: (source: string, target: string, length: number) => post<{ walks: string; note: string }>('/math/walks-exact', { source, target, length }),
  permutations: (n: number, k: number) => post<MathSeq>('/math/permutations', { n, k }),
  simplePaths: (source: string, target: string) => post<{ count: number; guard: string }>('/math/simple-paths', { source, target }),
  concepts: () => request<{ term: string; meaning: string }[]>('/math/concepts'),
}

export interface MathSeq {
  model: string; formula: string; sequence?: (number | string)[]; result?: string
  unit: string; assumptions: string; capped_at_retry?: number | null
}


export type ResearchAlgorithm = 'bfs' | 'dijkstra_static' | 'dijkstra_dynamic'
export interface ExperimentRequest {
  algorithms: ResearchAlgorithm[]; topology: 'current' | 'erdos_renyi' | 'small_world' | 'scale_free';
  node_count: number; source?: string; destination?: string; packet_count: number; duration_ms: number;
  packet_size_bytes: number; traffic_model: 'constant' | 'variable' | 'burst'; ttl: number;
  failures: FailureSchedule[]; security_enabled: boolean; tamper_rate: number; duplicate_rate: number;
  packet_expiry_ms: number; seed: number; repetitions: number
}
export interface MetricSummary { n: number; mean: number | null; stddev: number | null; median: number | null; ci95: [number, number] | null }
export interface ExperimentRunSummary {
  run_id: string; algorithm: ResearchAlgorithm; repetition: number; seed: number; metrics: Record<string, number | boolean | null>; packet_outcome_count: number
}
export interface ExperimentResult {
  comparison_id: string; created_at: string; config: ExperimentRequest; topology: GraphData;
  algorithms: ResearchAlgorithm[]; repetitions: number; paired_seed_policy: string; reference_algorithm: string;
  summaries: Record<string, Record<string, MetricSummary>>;
  paired_comparisons: Record<string, Record<string, MetricSummary & { comparison: string; matched_repetitions: number }>>;
  runs: Record<string, ExperimentRunSummary[]>; limitations: string[]
}
export interface ExperimentIndex { comparison_id: string; created_at: string; run_count: number; app_version: string }
export interface ExperimentDetail {
  comparison_id: string; algorithms: ResearchAlgorithm[]; repetitions: number; reference_algorithm: ResearchAlgorithm;
  summaries: Record<string, Record<string, MetricSummary>>;
  paired_comparisons: Record<string, Record<string, MetricSummary & { comparison: string; matched_repetitions: number }>>;
  runtime_provenance: { application_version?: string; python_version?: string; platform?: string; packages?: Record<string, string> };
  runs: { run_id: string; algorithm: ResearchAlgorithm; repetition: number; seed: number;
    created_at: string; config: ExperimentRequest; topology: GraphData;
    result: { metrics: Record<string, number | boolean | null>; packet_outcome_count: number }; app_version: string }[]
}

export interface PacketOutcome {
  packet_id: string; status: string; reason: string; generated_at_ms: number;
  finished_at_ms: number | null; hops: number; route_history: string[]; security?: Record<string, unknown> | null
}
export interface PacketOutcomePage { run_id: string; offset: number; limit: number; total: number; packets: PacketOutcome[] }
