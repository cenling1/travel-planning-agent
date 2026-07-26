import { beforeEach, describe, expect, it, vi } from 'vitest'
import { configureHttpClient, http } from './http'

describe('http client', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('sends FormData without forcing a JSON content type', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ documents: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    configureHttpClient({ getAccessToken: () => 'access', onUnauthorized: async () => false, clearAuth: vi.fn() })
    const form = new FormData()
    form.append('files', new Blob(['hello']), 'notes.txt')

    await http.upload('/api/documents', form)

    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(init.body).toBe(form)
    expect(new Headers(init.headers).has('Content-Type')).toBe(false)
  })

  it('shares one refresh across concurrent 401 responses and replays both requests', async () => {
    let calls = 0
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => {
      calls += 1
      if (calls <= 2) return new Response('{}', { status: 401 })
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })
    const refresh = vi.fn(async () => true)
    configureHttpClient({ getAccessToken: () => 'access', onUnauthorized: refresh, clearAuth: vi.fn() })

    const results = await Promise.all([http.get<{ ok: boolean }>('/api/a'), http.get<{ ok: boolean }>('/api/b')])

    expect(refresh).toHaveBeenCalledTimes(1)
    expect(results).toEqual([{ ok: true }, { ok: true }])
  })
})
