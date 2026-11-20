import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'
import type { Analysis } from '../types'

export default function TheoryTab() {
  const [a, setA] = useState<Analysis | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [ham, setHam] = useState<Record<string, string>>({})
  const [col, setCol] = useState<{ colors: Record<string, number>; num_colors: number; valid: boolean; note: string } | null>(null)
  const [trav, setTrav] = useState<string | null>(null)
  const [start, setStart] = useState('')
  const load = () => api.analysis().then((x) => { setA(x); setStart((s) => s || Object.keys(x.degrees)[0] || '') }).catch((e) => setErr(e.message))
  useEffect(() => { void load() }, [])
  const guard = async (fn: () => Promise<void>) => { setErr(null); try { await fn() } catch (e) { setErr(e instanceof ApiError ? e.message : String(e)) } }
  const hamRun = (kind: 'path' | 'cycle') => guard(async () => { const r = await api.hamiltonian(kind); setHam((h) => ({ ...h, [kind]: r.exists ? `Found: ${r.sequence!.join(' -> ')}` : `None. ${r.reason}` })) })
  if (!a) return <div className="panel">{err ?? 'Loading analysis...'}</div>
  return (
    <div className="space-y-4">
      {err && <div className="rounded border border-rose-600 bg-rose-950 p-2 text-sm" role="alert">{err}</div>}
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="panel text-sm"><h2>Degrees &amp; Handshaking Lemma</h2>
          <div className="mb-2 flex flex-wrap gap-2">{Object.entries(a.degrees).map(([n, d]) => <span key={n} className="badge bg-navy-700">{n}: {d}</span>)}</div>
          <div>Sum of degrees = <b>{a.handshake.degree_sum}</b>, 2 x edges = <b>{a.handshake.twice_edges}</b> -&gt; {a.handshake.holds ? 'holds' : 'VIOLATED'}</div>
          <div className="mt-2">Components ({a.component_count}): {a.components.map((c) => `{${c.join(', ')}}`).join(' ')}</div>
          <div>Isolated nodes: {a.isolated_nodes.length ? a.isolated_nodes.join(', ') : 'none'}</div>
        </section>
        <section className="panel text-sm"><h2>Eulerian (edges) vs Hamiltonian (vertices)</h2>
          <div>Euler: <b>{a.euler.classification}</b> - {a.euler.reason}</div>
          <div className="mt-3 flex gap-2"><button className="btn" onClick={() => void hamRun('path')}>Hamiltonian path</button><button className="btn" onClick={() => void hamRun('cycle')}>Hamiltonian cycle</button></div>
          {ham.path && <div className="mt-1 text-xs">Path: {ham.path}</div>}{ham.cycle && <div className="mt-1 text-xs">Cycle: {ham.cycle}</div>}
          <p className="mt-2 text-xs text-slate-400">Eulerian trails use every EDGE once; Hamiltonian paths visit every VERTEX once. Hamiltonian search is exponential and guarded to 10 nodes.</p>
        </section>
        <section className="panel text-sm"><h2>Greedy colouring</h2>
          <button className="btn" onClick={() => void guard(async () => setCol(await api.coloring()))}>Colour graph</button>
          {col && <div className="mt-2"><div>Colours used: <b>{col.num_colors}</b> - valid: <b>{String(col.valid)}</b></div>
            <div className="mt-1 flex flex-wrap gap-1.5">{Object.entries(col.colors).map(([n, c]) => <span key={n} className="badge" style={{ background: `hsl(${c * 67 + 180} 55% 32%)` }}>{n}: {c}</span>)}</div>
            <p className="mt-2 text-xs text-slate-400">{col.note}</p></div>}
        </section>
        <section className="panel text-sm"><h2>BFS / DFS traversal order</h2>
          <div className="flex gap-2"><select className="input" aria-label="Start node" value={start} onChange={(e) => setStart(e.target.value)}>{Object.keys(a.degrees).map((n) => <option key={n}>{n}</option>)}</select>
            {(['bfs', 'dfs'] as const).map((k) => <button key={k} className="btn" onClick={() => void guard(async () => setTrav(`${k.toUpperCase()}: ${(await api.traverse(k, start)).traversal_order.join(' -> ')}`))}>{k.toUpperCase()}</button>)}</div>
          {trav && <div className="mono mt-2 text-xs">{trav}</div>}
        </section>
      </div>
      <section className="panel overflow-auto text-xs"><h2>Adjacency matrix (weights)</h2>
        <table><thead><tr><th />{a.adjacency_matrix.labels.map((l) => <th key={l} className="px-2 text-slate-400">{l.slice(0, 6)}</th>)}</tr></thead>
          <tbody>{a.adjacency_matrix.matrix.map((row, i) => <tr key={i}><th className="pr-2 text-left text-slate-400">{a.adjacency_matrix.labels[i]}</th>{row.map((v, j) => <td key={j} className={`px-2 text-center ${v ? 'text-teal-300' : 'text-slate-600'}`}>{v}</td>)}</tr>)}</tbody></table>
        <h2 className="mt-4">Adjacency list</h2>
        {Object.entries(a.adjacency_list).map(([n, l]) => <div key={n}><b>{n}</b>: {l.map((x) => `${x.node}(${x.weight})`).join(', ') || '-'}</div>)}
      </section>
    </div>
  )
}
