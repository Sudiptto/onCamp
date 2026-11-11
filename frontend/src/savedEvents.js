import { ApiError, listSavedEvents, saveEvent, unsaveEvent } from './api.js'

export async function listSaved() {
  try {
    const body = await listSavedEvents()
    return (body.saved_events ?? []).map((row) => row.calendar).filter(Boolean)
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return []
    throw error
  }
}

export async function toggleSaved(event, saved) {
  if (!Number.isInteger(event.id)) {
    throw new Error('This event can no longer be saved.')
  }
  if (saved) await unsaveEvent(event.id)
  else await saveEvent(event.id)
  return listSaved()
}
