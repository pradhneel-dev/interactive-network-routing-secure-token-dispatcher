import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'

export default function NumberTheoryTab() {
  const [err, setErr] = useState<string | null>(null)
  const [out, setOut] = useState<Record<string, string>>({})
  const [v, setV] = useState<Record<string, string>>({ a: '240', b: '46', m: '11', base: '4', exp: '13', mod: '497', msg: '65' })
  const [keys, setKeys] = useState<Awaited<ReturnType<typeof api.keys>> | null>(null)
  const [nodes, setNodes] = useState<string[]>([])
  const [tk, setTk] = useState({ src: '', dst: '', payload: 'secret-ish payload' })
  const [token, setToken] = useState<Record<string, unknown> | null>(null)
  const [tamper, setTamper] = useState<'none' | 'payload' | 'route' | 'signature'>('none')
  const n = (k: string) => Number(v[k])
  const set = (k: string, val: string) => setV((s) => ({ ...s, [k]: val }))
  useEffect(() => { api.getGraph().then((g) => { const ids = g.nodes.map((x) => x.id); setNodes(ids); setTk((t) => ({ ...t, src: ids[0] ?? '', dst: ids[1] ?? '' })) }).catch(() => undefined) }, [])
  const go = async (key: string, fn: () => Promise<string>) => { setErr(null); try { setOut((o) => ({ ...o, [key]: '' })); const r = await fn(); setOut((o) => ({ ...o, [key]: r })) } catch (e) { setErr(e instanceof ApiError ? e.message : String(e)) } }
  const inp = (k: string, label: string) => <div><label className="label" htmlFor={`nt-${k}`}>{label}</label><input id={`nt-${k}`} className="input w-24" value={v[k]} onChange={(e) => set(k, e.target.value)} /></div>
  const createTok = () => go('tok', async () => { const r = await api.tokenCreate(tk.src, tk.dst, tk.payload); setToken(r.token); return `Token ${String(r.token.token_id)} created (route ${(r.token.route as string[]).join(' -> ')}).` })
  const verifyTok = () => go('ver', async () => {
    if (!token) throw new Error('Create a token first.')
    let t = { ...token }; let payload = tk.payload
    const header: Record<string, unknown> = { packet_id: t.packet_id, seq: t.seq, source: t.source, destination: t.destination, route: t.route }
    if (tamper === 'payload') payload += '!'
    if (tamper === 'route') header.route = [...(t.route as string[]).slice(0, -1), 'Rogue-Router', t.destination]
    if (tamper === 'signature') t = { ...t, signature: Number(t.signature) + 1 }
    const r = await api.tokenVerify(t, payload, header)
    return `${r.valid ? 'VALID' : 'REJECTED'} - ${r.status}. ${r.reasons.join(' ')}`
  })
  return (
    <div className="space-y-4">
      <div className="rounded border border-amber-700 bg-amber-950 p-2 text-sm text-amber-200">Academic/toy cryptography - small keys, no padding. NOT production security.</div>
      {err && <div className="rounded border border-rose-600 bg-rose-950 p-2 text-sm" role="alert">{err}</div>}
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="panel text-sm"><h2>GCD &amp; Extended Euclid</h2><div className="flex items-end gap-2">{inp('a', 'a')}{inp('b', 'b')}
          <button className="btn" onClick={() => void go('gcd', async () => { const r = await api.gcd(n('a'), n('b')); return `gcd = ${r.gcd}; steps: ${r.steps.map((s) => `${s.a} = ${s.q}x${s.b} + ${s.r}`).join('; ')}` })}>GCD</button>
          <button className="btn" onClick={() => void go('gcd', async () => { const r = await api.egcd(n('a'), n('b')); return `${r.identity} (Bezout ${r.verified ? 'verified' : 'FAILED'})` })}>Extended</button></div>
          <div className="mono mt-2 text-xs">{out.gcd}</div></section>
        <section className="panel text-sm"><h2>Modular inverse &amp; exponentiation</h2><div className="flex items-end gap-2">{inp('m', 'modulus m')}
          <button className="btn" onClick={() => void go('mi', async () => { const r = await api.modinv(n('a'), n('m')); return `a^-1 mod m = ${r.inverse} (${r.check})` })}>Inverse of a</button></div>
          <div className="mt-2 flex items-end gap-2">{inp('base', 'base')}{inp('exp', 'exp')}{inp('mod', 'mod')}
            <button className="btn" onClick={() => void go('mi', async () => `base^exp mod mod = ${(await api.modexp(n('base'), n('exp'), n('mod'))).result}`)}>Mod-exp</button></div>
          <div className="mono mt-2 text-xs">{out.mi}</div></section>
        <section className="panel text-sm"><h2>Toy RSA keys, encrypt, decrypt</h2>
          <button className="btn" onClick={() => void go('k', async () => { const k = await api.keys({ bits: 24 }); setKeys(k); return 'Key pair generated.' })}>Generate keys (24-bit primes)</button>
          {keys && <ol className="mono mt-2 list-decimal pl-5 text-xs">{keys.steps.map((s) => <li key={s}>{s}</li>)}</ol>}
          {keys && <div className="mt-2 flex items-end gap-2">{inp('msg', 'message m (< n)')}
            <button className="btn" onClick={() => void go('rsa', async () => { const c = (await api.encrypt(n('msg'), keys.n, keys.public.e)).ciphertext; const p = (await api.decrypt(c, keys.n, keys.private.d)).plaintext; return `c = m^e mod n = ${c}; m = c^d mod n = ${p} (${p === n('msg') ? 'round trip OK' : 'MISMATCH'})` })}>Encrypt + decrypt</button></div>}
          <div className="mono mt-2 text-xs">{out.k} {out.rsa}</div></section>
        <section className="panel text-sm"><h2>Token create / verify</h2>
          <div className="flex gap-2"><select className="input" aria-label="Token source" value={tk.src} onChange={(e) => setTk({ ...tk, src: e.target.value })}>{nodes.map((x) => <option key={x}>{x}</option>)}</select>
            <select className="input" aria-label="Token destination" value={tk.dst} onChange={(e) => setTk({ ...tk, dst: e.target.value })}>{nodes.map((x) => <option key={x}>{x}</option>)}</select></div>
          <input className="input mt-2 w-full" aria-label="Token payload" value={tk.payload} onChange={(e) => setTk({ ...tk, payload: e.target.value })} />
          <div className="mt-2 flex flex-wrap items-center gap-2"><button className="btn" onClick={() => void createTok()}>Create token</button>
            <select className="input" aria-label="Tamper" value={tamper} onChange={(e) => setTamper(e.target.value as typeof tamper)}><option value="none">No tampering</option><option value="payload">Tamper payload</option><option value="route">Tamper route</option><option value="signature">Tamper signature</option></select>
            <button className="btn" onClick={() => void verifyTok()}>Verify</button></div>
          <div className="mt-2 text-xs">{out.tok}</div><div className="mt-1 text-xs">{out.ver}</div></section>
      </div>
    </div>
  )
}
