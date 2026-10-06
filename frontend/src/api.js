async function readJson(response) {
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(body.error || `Events API returned ${response.status}`)
  }
  return body
}

async function getJson(path) {
  try {
    return await readJson(await fetch(path))
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
  const [upcoming, archive] = await Promise.all([
    getJson('/api/events'),
    getJson('/api/events/archive'),
  ])
  const clubs = new Map()
  for (const event of [...upcoming.events, ...archive.events]) {
    clubs.set(event.club_id, event.club_name)
  }
  return [...clubs.entries()]
    .map(([id, name]) => ({ id, name }))
    .sort((a, b) => a.name.localeCompare(b.name))
}
