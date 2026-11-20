import { describe, expect, it } from 'vitest'
import { frameState, reportMatchesResults, scenarioToOptions, summarizeResults, traceView } from '../lib'
import type { DispatchEvent, PacketResult, Report, TraceStep } from '../types'

const step = (i: number, extra: Partial<TraceStep>): TraceStep => ({ index: i, kind: 'x', message: '', current: null, edge: null, visited: [], processed: [], frontier: [], frontier_type: 'queue', ...extra })

describe('trace view is derived from the returned trace', () => {
  const steps = [
    step(0, { current: 'A', visited: ['A'], frontier: ['A'] }),
    step(1, { current: 'A', edge: ['A', 'B'], visited: ['A', 'B'], frontier: ['B'] }),
    step(2, { current: 'B', edge: ['B', 'C'], visited: ['A', 'B', 'C'], processed: ['A', 'B'], frontier: [['C', 7]], frontier_type: 'priority_queue' }),
  ]
  it('is empty before start', () => expect(traceView(steps, -1).step).toBeNull())
  it('accumulates explored edges and shows state at the step', () => {
    const v = traceView(steps, 2)
    expect([...v.visited]).toEqual(['A', 'B', 'C'])
    expect(v.explored.size).toBe(2)
    expect(v.frontierLabels).toEqual(['C (7)'])
    expect(v.current).toBe('B')
  })
  it('clamps beyond the end', () => expect(traceView(steps, 99).step?.index).toBe(2))
})

const ev = (i: number, kind: DispatchEvent['kind'], seq: number, from: string, to: string): DispatchEvent => ({ index: i, kind, packet_id: `P-${seq}`, seq, from, to, hop: i, status: '', message: '' })

describe('packet animation follows the computed route', () => {
  const route = ['A', 'B', 'C']
  const events = [ev(0, 'send', 1, 'A', 'A'), ev(1, 'hop', 1, 'A', 'B'), ev(2, 'hop', 1, 'B', 'C'), ev(3, 'arrived', 1, 'B', 'C'), ev(4, 'send', 2, 'A', 'A'), ev(5, 'dropped', 2, 'A', 'B')]
  it('hop events chain exactly along the route', () => {
    const hops = events.filter((e) => e.kind === 'hop' && e.seq === 1)
    expect([hops[0].from, ...hops.map((h) => h.to)]).toEqual(route)
  })
  it('tracks packet position and active edge per frame', () => {
    expect(frameState(events, 1).positions[1]).toBe('B')
    expect(frameState(events, 1).activeEdge).toEqual(['A', 'B'])
    expect(frameState(events, 3).positions[1]).toBe('C')
  })
  it('a dropped packet has no position', () => {
    const f = frameState(events, 5)
    expect(f.positions[2]).toBeNull()
    expect(f.event?.kind).toBe('dropped')
  })
})

describe('scenario controls change the real request', () => {
  it('maps per-packet scenarios to API options', () => {
    const o = scenarioToOptions({ 1: 'normal', 2: 'drop', 3: 'tamper_payload', 4: 'tamper_route', 5: 'tamper_token', 6: 'duplicate' }, 1)
    expect(o).toEqual({ drop_seqs: [2], drop_count: 1, tamper_payload_seqs: [3], tamper_route_seqs: [4], tamper_token_seqs: [5], duplicate_seqs: [6] })
  })
})

describe('report values match simulation state', () => {
  const mk = (seq: number, status: string, received = true): PacketResult => ({ packet_id: `P${seq}`, seq, received, verified: status === 'Delivered & Verified', status, checks: null, reasons: [], explanation: '', duplicate_copies: 0 })
  const results = [mk(1, 'Delivered & Verified'), mk(2, 'Lost/Missing', false), mk(3, 'Payload Modified'), mk(4, 'Metadata Tampered'), mk(5, 'Delivered & Verified')]
  it('summarises counts and percentage', () => {
    expect(summarizeResults(results)).toMatchObject({ sent: 5, received: 4, lost: 1, verified: 2, integrity: 1, metadata: 1, signature: 0, pct: 40 })
  })
  it('detects a report that disagrees with the results', () => {
    const base = { packets_sent: 5, packets_received: 4, packets_lost: 1, delivered_verified: 2, integrity_failures: 1, signature_failures: 0, metadata_failures: 1, delivery_percentage: 40 } as Report
    expect(reportMatchesResults(base, results)).toBe(true)
    expect(reportMatchesResults({ ...base, delivery_percentage: 100 }, results)).toBe(false)
  })
})
