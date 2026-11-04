function storageKey(userId) {
  return `oncamp.saved-events:${userId}`
}

function readSaved(userId) {
  try {
    const raw = localStorage.getItem(storageKey(userId))
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function writeSaved(userId, events) {
  localStorage.setItem(storageKey(userId), JSON.stringify(events))
  return events
}

export async function listSaved(userId) {
  // TODO: GET /api/saved-events once that route exists.
  return readSaved(userId)
}

export async function toggleSaved(userId, event) {
  // TODO: POST /api/saved-events and DELETE /api/saved-events/:eventId
  const current = readSaved(userId)
  const alreadySaved = current.some((item) => item.event_id === event.event_id)
  const next = alreadySaved
    ? current.filter((item) => item.event_id !== event.event_id)
    : [...current, event]
  return writeSaved(userId, next)
}
