import { afterEach, describe, expect, it, vi } from 'vitest'
import { API_URL, ApiError, request } from '../api'

afterEach(() => vi.unstubAllGlobals())

describe('api client', () => {
  it('uses the documented backend port by default (or VITE_API_URL)', () => {
    expect(API_URL).toBe(import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8002')
    expect(API_URL).toContain(':8002')
  })
  it('turns a structured backend error into ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 400, statusText: 'Bad', json: async () => ({ error: { code: 'negative_weight', message: 'Negative edge weights are rejected' } }) }))
    await expect(request('/graph/edges', { method: 'POST', body: {} })).rejects.toMatchObject({ code: 'negative_weight', status: 400 })
  })
  it('reports a disconnected backend instead of faking data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('failed')))
    const err = (await request('/graph').catch((e) => e)) as ApiError
    expect(err).toBeInstanceOf(ApiError)
    expect(err.code).toBe('disconnected')
    expect(err.message).toContain(API_URL)
  })
})
