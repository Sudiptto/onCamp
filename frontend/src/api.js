export class ApiError extends Error {
  constructor(message, status, code) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function readJson(response) {
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new ApiError(body.error || `Events API returned ${response.status}`, response.status, body.code)
  }
  return body
}

async function getJson(path) {
  try {
    return await readJson(await fetch(path, { credentials: 'include' }))
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error('Could not reach the events API. Start the backend on port 5000.')
    }
    throw error
  }
}

export function fetchEvents({ mode, range, clubId }) {
  const params = new URLSearchParams()
  if (clubId) params.set('club_id', clubId)

  if (mode === 'archive') {
    const query = params.toString()
    return getJson(`/api/events/archive${query ? `?${query}` : ''}`)
  }

  if (range === 'all' && !clubId) {
    return getJson('/api/events')
  }

  params.set('range', range)
  return getJson(`/api/events/filter?${params.toString()}`)
}

export async function fetchClubOptions() {
  // archive needs a login, so logged out people only get clubs from upcoming events
  const [upcoming, archive] = await Promise.allSettled([
    getJson('/api/events'),
    getJson('/api/events/archive'),
  ])
  if (upcoming.status === 'rejected') throw upcoming.reason
  const archiveEvents = archive.status === 'fulfilled' ? archive.value.events : []
  const clubs = new Map()
  for (const event of [...upcoming.value.events, ...archiveEvents]) {
    clubs.set(event.club_id, event.club_name)
  }
  return [...clubs.entries()]
    .map(([id, name]) => ({ id, name }))
    .sort((a, b) => a.name.localeCompare(b.name))
}


// Auth requests send the session cookie plus a CSRF header.
let csrfToken = ''

async function authRequest(path, options = {}) {
  let response
  try {
    response = await fetch(path, {
      ...options,
      credentials: 'include',
      headers: {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options.headers || {}),
      },
    })
  } catch {
    throw new ApiError('Could not reach onCamp. Check your connection and try again.', 0)
  }
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new ApiError(body.error || `Request failed (${response.status})`, response.status, body.code)
  if (body.csrf_token) csrfToken = body.csrf_token
  return body
}

async function ensureCsrfToken() {
  if (csrfToken) return csrfToken
  const body = await authRequest('/api/auth/csrf')
  csrfToken = body.csrf_token
  return csrfToken
}

async function postAuth(path, values = {}) {
  const send = async () =>
    authRequest(path, {
      method: 'POST',
      headers: { 'X-CSRF-Token': await ensureCsrfToken() },
      body: JSON.stringify(values),
    })
  try {
    return await send()
  } catch (error) {
    // 403 usually means the CSRF token went stale, so grab a new one and try once more
    if (error.status === 403) {
      csrfToken = ''
      return send()
    }
    throw error
  }
}

export async function getCurrentUser() {
  await ensureCsrfToken()
  const result = await authRequest('/api/auth/me')
  return result.user
}

// credential is the token the Google button gives us. The server checks it.
export function loginWithGoogle(credential) {
  return postAuth('/api/auth/google', { credential })
}

export function logoutAccount() {
  return postAuth('/api/auth/logout')
}
