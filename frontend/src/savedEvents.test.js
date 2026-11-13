import assert from 'node:assert/strict'
import { describe, test } from 'node:test'

import { listSaved, toggleSaved } from './savedEvents.js'

const card = { id: 12, event_id: 'post:12', event_name: 'Intro to Git' }

function mockFetch(handler) {
  const originalFetch = globalThis.fetch
  const calls = []
  globalThis.fetch = async (path, options = {}) => {
    calls.push({ path, options })
    return handler(path, options)
  }
  return {
    calls,
    restore() {
      globalThis.fetch = originalFetch
    },
  }
}

function jsonResponse(body, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

describe('saved events API', { concurrency: false }, () => {
test('saved events come back in the calendar card shape', async (t) => {
  const client = mockFetch((path) => {
    assert.equal(path, '/api/saved-events')
    return jsonResponse({ saved_events: [{ calendar: card }, { calendar: null }] })
  })
  t.after(() => client.restore())

  assert.deepEqual(await listSaved(), [card])
  assert.equal(client.calls[0].options.credentials, 'include')
})

test('a signed-out saved list is empty', async (t) => {
  const client = mockFetch(() => jsonResponse({ error: 'Sign in to continue.', code: 'login_required' }, 401))
  t.after(() => client.restore())
  assert.deepEqual(await listSaved(), [])
})

test('saving sends the integer event id and the CSRF header', async (t) => {
  const client = mockFetch((path, options) => {
    if (path === '/api/auth/csrf') return jsonResponse({ csrf_token: 'tok' })
    if (options.method === 'POST') return jsonResponse({ created: true }, 201)
    return jsonResponse({ saved_events: [{ calendar: card }] })
  })
  t.after(() => client.restore())

  assert.deepEqual(await toggleSaved({ id: 12, event_id: 'post:12' }, false), [card])
  const post = client.calls.find((call) => call.options.method === 'POST')
  assert.equal(post.path, '/api/saved-events')
  assert.equal(post.options.headers['X-CSRF-Token'], 'tok')
  assert.equal(post.options.body, JSON.stringify({ event_id: 12 }))
})

test('unsaving deletes that event id', async (t) => {
  const client = mockFetch((path, options) => {
    if (path === '/api/auth/csrf') return jsonResponse({ csrf_token: 'tok' })
    if (options.method === 'DELETE') return { ok: true, status: 204, json: async () => { throw new Error('no body') } }
    return jsonResponse({ saved_events: [] })
  })
  t.after(() => client.restore())

  assert.deepEqual(await toggleSaved(card, true), [])
  const deleted = client.calls.find((call) => call.options.method === 'DELETE')
  assert.equal(deleted.path, '/api/saved-events/12')
  assert.equal(deleted.options.headers['X-CSRF-Token'], 'tok')
})

test('an archived event cannot be saved', async () => {
  await assert.rejects(toggleSaved({ id: null, event_id: 'post:old' }, false), /no longer be saved/)
})
})
