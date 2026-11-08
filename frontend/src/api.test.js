import assert from 'node:assert/strict'
import test from 'node:test'

import { fetchClubOptions, fetchEvents } from './api.js'

test('calendar requests the filtered events API with session credentials', async (t) => {
  const originalFetch = globalThis.fetch
  t.after(() => { globalThis.fetch = originalFetch })
  const calls = []
  globalThis.fetch = async (path, options) => {
    calls.push({ path, options })
    return { ok: true, json: async () => ({ events: [{ event_id: 'post:1' }] }) }
  }
  const result = await fetchEvents({ mode: 'upcoming', range: '2w', clubId: '4' })
  assert.equal(calls[0].path, '/api/events/filter?club_id=4&range=2w')
  assert.equal(calls[0].options.credentials, 'include')
  assert.equal(result.events[0].event_id, 'post:1')
  await fetchEvents({ mode: 'archive', range: 'all', clubId: '' })
  assert.equal(calls[1].path, '/api/events/archive')
})

test('club options do not request the authenticated archive for visitors', async (t) => {
  const originalFetch = globalThis.fetch
  t.after(() => { globalThis.fetch = originalFetch })
  const calls = []
  globalThis.fetch = async (path) => {
    calls.push(path)
    return { ok: true, json: async () => ({ events: [{ club_id: '1', club_name: 'Coding' }] }) }
  }
  assert.deepEqual(await fetchClubOptions(), [{ id: '1', name: 'Coding' }])
  assert.deepEqual(calls, ['/api/events'])
  await fetchClubOptions({ includeArchive: true })
  assert.deepEqual(calls, ['/api/events', '/api/events', '/api/events/archive'])
})

test('club option errors are surfaced', async (t) => {
  const originalFetch = globalThis.fetch
  t.after(() => { globalThis.fetch = originalFetch })
  globalThis.fetch = async (path) => path.endsWith('/archive')
    ? { ok: false, status: 500, json: async () => ({ error: 'Archive unavailable' }) }
    : { ok: true, json: async () => ({ events: [] }) }
  await assert.rejects(fetchClubOptions({ includeArchive: true }), /Archive unavailable/)
})
