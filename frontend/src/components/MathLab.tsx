import { useEffect, useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, ApiError, type MathSeq } from '../api'

type ModelId = 'additive' | 'backoff' | 'fibonacci' | 'walks' | 'permutations' | 'paths' | 'concepts'
interface Field { key: string; label: string; def: string; optional?: boolean }
const MODELS: { id: ModelId; name: string; fields: Field[] }[] = [
  { id: 'additive', name: 'Additive traffic growth', fields: [{ key: 'initial', label: 'Initial T0 (packets)', def: '100' }, { key: 'k', label: 'Increment k', def: '25' }, { key: 'steps', label: 'Steps', def: '10' }] },
  { id: 'backoff', name: 'Exponential backoff', fields: [{ key: 'delay', label: 'Initial delay D0 (ms)', def: '100' }, { key: 'r', label: 'Multiplier r', def: '2' }, { key: 'steps', label: 'Retries', def: '8' }, { key: 'cap', label: 'Cap (ms, optional)', def: '', optional: true }] },
  { id: 'fibonacci', name: 'Fibonacci', fields: [{ key: 'n', label: 'n', def: '15' }, { key: 'f0', label: 'F0', def: '0' }, { key: 'f1', label: 'F1', def: '1' }] },
  { id: 'walks', name: 'Walk counting (regular branching)', fields: [{ key: 'd', label: 'Branching factor d', def: '3' }, { key: 'steps', label: 'Steps n', def: '6' }] },
  { id: 'permutations', name: 'k-permutations', fields: [{ key: 'n', label: 'n', def: '6' }, { key: 'k', label: 'k', def: '3' }] },
  { id: 'paths', name: 'Simple-path counting (current graph)', fields: [{ key: 'source', label: 'Source', def: 'Main Gate' }, { key: 'target', label: 'Target', def: 'Data Center' }] },
  { id: 'concepts', name: 'Walk vs path vs route', fields: [] },
]

export default function MathLab() {
  const [model, setModel] = useState<ModelId>('additive')
  const [vals, setVals] = useState<Record<string, string>>({})
  const [res, setRes] = useState<MathSeq | null>(null)
  const [extra, setExtra] = useState<string | null>(null)
  const [paths, setPaths] = useState<{ count: number; guard: string } | null>(null)
  const [concepts, setConcepts] = useState<{ term: string; meaning: string }[]>([])
  const [err, setErr] = useState<string | null>(null)
  const m = MODELS.find((x) => x.id === model)!
  const get = (f: Field) => vals[`${model}.${f.key}`] ?? f.def
  const num = (key: string) => Number(get(m.fields.find((f) => f.key === key)!))

  useEffect(() => { setRes(null); setExtra(null); setPaths(null); setErr(null) }, [model])
  useEffect(() => { if (model === 'concepts' && concepts.length === 0) api.concepts().then(setConcepts).catch((e) => setErr(String(e.message ?? e))) }, [model, concepts.length])

  const calc = async () => {
    setErr(null); setExtra(null)
    try {
      if (model === 'additive') setRes(await api.additive(num('initial'), num('k'), num('steps')))
      if (model === 'backoff') { const c = get(m.fields[3]); setRes(await api.backoff(num('delay'), num('r'), num('steps'), c === '' ? null : Number(c))) }
      if (model === 'fibonacci') setRes(await api.fibonacci(num('n'), num('f0'), num('f1')))
      if (model === 'walks') {
        setRes(await api.walks(num('d'), num('steps')))
        try { const x = await api.walksExact(get(MODELS[5].fields[0]), get(MODELS[5].fields[1]), num('steps')); setExtra(`Exact walks of length ${num('steps')} in the CURRENT graph from ${get(MODELS[5].fields[0])} to ${get(MODELS[5].fields[1])}: ${x.walks}. ${x.note}`) } catch { /* optional comparison */ }
      }
      if (model === 'permutations') setRes(await api.permutations(num('n'), num('k')))
      if (model === 'paths') { setRes(null); setPaths(await api.simplePaths(get(m.fields[0]), get(m.fields[1]))) }
    } catch (e) { setRes(null); setErr(e instanceof ApiError ? e.message : String(e)) }
  }

  const data = (res?.sequence ?? []).map((v, i) => ({ n: i, value: Number(v) }))
  return (
    <div className="space-y-4">
      <div className="panel text-sm text-slate-300">Unit 4 - Recurrence Relations and Counting. A secondary lab: every sequence and chart below is calculated by the backend from your current inputs.</div>
      <div className="grid gap-4 lg:grid-cols-3">
        <section className="panel">
          <h2>Model</h2>
          <label className="label" htmlFor="model">Select model</label>
          <select id="model" className="input w-full" value={model} onChange={(e) => setModel(e.target.value as ModelId)}>{MODELS.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>
          <div className="mt-3 space-y-2">
            {m.fields.map((f) => (<div key={f.key}><label className="label" htmlFor={`f-${f.key}`}>{f.label}</label>
              <input id={`f-${f.key}`} className="input w-full" value={get(f)} onChange={(e) => setVals((v) => ({ ...v, [`${model}.${f.key}`]: e.target.value }))} /></div>))}
          </div>
          {model !== 'concepts' && <button className="btn btn-primary mt-3" onClick={() => void calc()}>Calculate</button>}
        </section>
        <section className="panel lg:col-span-2" data-testid="math-output">
          <h2>{m.name}</h2>
          {err && <div className="rounded border border-rose-600 bg-rose-950 p-2 text-sm" role="alert">{err}</div>}
          {model === 'concepts' && <dl className="space-y-2 text-sm">{concepts.map((c) => <div key={c.term}><dt className="font-semibold text-teal-300">{c.term}</dt><dd className="text-slate-300">{c.meaning}</dd></div>)}</dl>}
          {paths && <div className="text-sm"><div>Simple paths: <b data-testid="path-count">{paths.count}</b></div><div className="text-xs text-slate-400">Backtracking is exponential; guard: {paths.guard}</div></div>}
          {res && (<div className="space-y-2 text-sm">
            <div className="mono rounded bg-navy-900 p-2 text-teal-200" data-testid="formula">{res.formula}</div>
            <div className="text-xs text-slate-400">Unit: {res.unit}. Assumptions: {res.assumptions}</div>
            {res.capped_at_retry !== undefined && res.capped_at_retry !== null && <div className="text-xs text-amber-300">Cap reached at retry {res.capped_at_retry}.</div>}
            {res.result !== undefined && <div>Result: <b className="mono" data-testid="result">{res.result}</b></div>}
            {extra && <div className="rounded bg-navy-900 p-2 text-xs text-amber-200">{extra}</div>}
            {res.sequence && (<>
              <div className="h-56" data-testid="chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={data}><CartesianGrid stroke="#1f2c47" /><XAxis dataKey="n" stroke="#94a3b8" /><YAxis stroke="#94a3b8" /><Tooltip contentStyle={{ background: '#0b1220', border: '1px solid #25365a' }} /><Line type="monotone" dataKey="value" stroke="#2dd4bf" dot /></LineChart></ResponsiveContainer></div>
              <div className="mono max-h-28 overflow-auto text-xs" data-testid="sequence">{res.sequence.map((v, i) => `${m.id === 'backoff' ? 'D' : m.id === 'fibonacci' ? 'F' : 'T'}${i}=${v}`).join(', ')}</div></>)}
          </div>)}
        </section>
      </div>
    </div>
  )
}
