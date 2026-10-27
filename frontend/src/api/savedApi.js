function storageKey(email) {
  return `oncamp.saved-events:${email}`
}

function readSaved(email) {
  try {
    return JSON.parse(localStorage.getItem(storageKey(email)) || '[]')
  } catch {
    return []
  }
}

function writeSaved(email, events) {
  localStorage.setItem(storageKey(email), JSON.stringify(events))
  return events
}

export async function listSaved(email) {
  // TODO: GET /api/saved-events
  // const response = await fetch('/api/saved-events')
  return readSaved(email)
}

export async function saveEvent(email, event) {
  // TODO: POST /api/saved-events
  // await fetch('/api/saved-events', { method: 'POST', body: JSON.stringify({ event_id: event.event_id }) })
  const current = readSaved(email)
  if (current.some((item) => item.event_id === event.event_id)) return current
  return writeSaved(email, [...current, event])
}

export async function unsaveEvent(email, eventId) {
  // TODO: DELETE /api/saved-events/:eventId
  // await fetch(`/api/saved-events/${eventId}`, { method: 'DELETE' })
  return writeSaved(
    email,
    readSaved(email).filter((item) => item.event_id !== eventId),
  )
}

export async function toggleSaved(email, event) {
  const current = readSaved(email)
  if (current.some((item) => item.event_id === event.event_id)) {
    return unsaveEvent(email, event.event_id)
  }
  return saveEvent(email, event)
}
