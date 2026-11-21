import { daysUntil, toISODate } from './dates.js'

export const QUICK_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'food', label: 'Free Food' },
  { id: 'today', label: 'Today' },
  { id: 'week', label: 'This Week' },
  { id: 'tonight', label: 'Tonight' },
]

const TONIGHT_HOUR = 17 // 5 PM and later counts as tonight
const DEFAULT_LENGTH_MINUTES = 60 // same default the calendar export uses

function toMinutes(time) {
  if (!time) return null
  const [hour, minute] = time.split(':').map(Number)
  return Number.isNaN(hour) ? null : hour * 60 + (minute || 0)
}

// date-only posts are saved at 00:00 with no end time, so that isn't a real start time
export function hasClockTime(event) {
  return Boolean(event.start_time) && !(event.start_time === '00:00' && !event.end_time)
}

export function formatClock(time) {
  const [hourValue, minute] = time.split(':').map(Number)
  const hour = hourValue % 12 || 12
  return `${hour}${minute ? `:${String(minute).padStart(2, '0')}` : ''} ${hourValue >= 12 ? 'PM' : 'AM'}`
}

function endMinutes(event) {
  const start = toMinutes(event.start_time)
  const end = toMinutes(event.end_time)
  return end !== null && end > start ? end : start + DEFAULT_LENGTH_MINUTES
}

export function matchesQuickFilter(event, filter, now = new Date()) {
  const today = toISODate(now)
  if (filter === 'food') return Boolean(event.free_food)
  if (filter === 'today') return event.date === today
  if (filter === 'week') return daysUntil(event.date, today) >= 0 && daysUntil(event.date, today) <= 6
  if (filter === 'tonight') return event.date === today && (toMinutes(event.start_time) ?? 0) >= TONIGHT_HOUR * 60
  return true
}

export function sortEvents(events) {
  const key = (event) => `${event.date} ${event.start_time || ''}`
  return [...events].sort((a, b) => (key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : 0))
}

// "Starting in 45 min", "Tomorrow at 1 PM", "Saturday at 2 PM", "Dec 3 at 6 PM"
export function whenLabel(event, now = new Date()) {
  const days = daysUntil(event.date, toISODate(now))
  const timed = hasClockTime(event)
  const at = timed ? ` at ${formatClock(event.start_time)}` : ''

  if (days === 0) {
    if (!timed) return 'Today'
    const start = toMinutes(event.start_time)
    const current = now.getHours() * 60 + now.getMinutes()
    if (current >= start && current < endMinutes(event)) return 'Happening now'
    if (current > start) return `Earlier today${at}`
    return start - current <= 90 ? `Starting in ${start - current} min` : `Today${at}`
  }

  const [year, month, day] = event.date.split('-').map(Number)
  const date = new Date(year, month - 1, day)
  if (days === 1) return `Tomorrow${at}`
  if (days > 1 && days < 7) return `${date.toLocaleDateString('en-US', { weekday: 'long' })}${at}`
  return `${date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}${at}`
}

// first event today that hasn't finished yet, used for the big card on Home
export function pickFeatured(events, now = new Date()) {
  const today = toISODate(now)
  const current = now.getHours() * 60 + now.getMinutes()
  return events.find((event) => event.date === today && (!hasClockTime(event) || current < endMinutes(event))) ?? null
}

export function countFoodThisWeek(events, now = new Date()) {
  return events.filter((event) => event.free_food && matchesQuickFilter(event, 'week', now)).length
}

export function instagramHandle(link) {
  const match = /instagram\.com\/([^/?#]+)/i.exec(link || '')
  return match ? match[1] : ''
}

// photos, handles and counts come from the events we already loaded, the club list only has ids and names
export function summarizeClubs(events, clubs, today) {
  const info = new Map()
  for (const event of events) {
    const row = info.get(event.club_id) ?? { pfp: event.club_pfp, link: event.club_link, upcoming: 0 }
    if (event.date >= today) row.upcoming += 1
    info.set(event.club_id, row)
  }
  return clubs
    .map((club) => ({ id: club.id, name: club.name, pfp: info.get(club.id)?.pfp ?? '', handle: instagramHandle(info.get(club.id)?.link), upcoming: info.get(club.id)?.upcoming ?? 0 }))
    .sort((a, b) => b.upcoming - a.upcoming || a.name.localeCompare(b.name))
}

// one entry per date, events keep their order (they come in already sorted)
export function groupByDate(events) {
  const days = []
  for (const event of events) {
    const last = days[days.length - 1]
    if (last && last.date === event.date) last.events.push(event)
    else days.push({ date: event.date, events: [event] })
  }
  return days
}

// club ids are numbers on events but strings once they've been through a <select>, so compare as strings
export const sameClub = (a, b) => String(a) === String(b)

export function moreFromClub(events, event, limit = 3) {
  return events.filter((other) => sameClub(other.club_id, event.club_id) && other.event_id !== event.event_id).slice(0, limit)
}
