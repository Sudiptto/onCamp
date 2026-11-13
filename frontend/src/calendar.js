// Event times come from the backend as campus local time with no timezone.
const CAMPUS_TIMEZONE = 'America/New_York'

// Events with no end time get a one hour slot so they don't show up as 0 minutes long.
const DEFAULT_LENGTH_MINUTES = 60

function pad(value) {
  return String(value).padStart(2, '0')
}

// Formats a Date as YYYYMMDD or YYYYMMDDTHHMMSS. It reads the UTC fields on purpose,
// the dates below are built with Date.UTC so the browser's timezone can't shift them.
function stamp(date, withTime) {
  const day = `${date.getUTCFullYear()}${pad(date.getUTCMonth() + 1)}${pad(date.getUTCDate())}`
  if (!withTime) return day
  return `${day}T${pad(date.getUTCHours())}${pad(date.getUTCMinutes())}00`
}

function parseStart(event) {
  const [year, month, day] = event.date.split('-').map(Number)
  const [hour, minute] = (event.start_time || '00:00').split(':').map(Number)
  return new Date(Date.UTC(year, month - 1, day, hour, minute))
}

export function calendarWindow(event) {
  const start = parseStart(event)

  // Date-only posts are stored at 00:00 with no end time, so show them as all day
  // instead of an event at midnight.
  const allDay = !event.end_time && (!event.start_time || event.start_time === '00:00')
  if (allDay) {
    const nextDay = new Date(start.getTime() + 24 * 60 * 60 * 1000)
    return { allDay, start: stamp(start, false), end: stamp(nextDay, false) }
  }

  let end = new Date(start.getTime() + DEFAULT_LENGTH_MINUTES * 60 * 1000)
  if (event.end_time) {
    const [hour, minute] = event.end_time.split(':').map(Number)
    const candidate = new Date(
      Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate(), hour, minute),
    )
    // Only the clock time is sent for the end, so an end before the start has to be
    // past midnight or a typo. Keep the default slot rather than guess.
    if (candidate > start) end = candidate
  }
  return { allDay, start: stamp(start, true), end: stamp(end, true) }
}

function description(event) {
  const lines = [`Hosted by ${event.club_name}.`]
  if (event.free_food) lines.push('Free food!')
  if (event.post_link) lines.push(`Original post: ${event.post_link}`)
  if (event.event_link) lines.push(`Sign up: ${event.event_link}`)
  return lines.join('\n')
}

export function googleCalendarUrl(event) {
  const { start, end } = calendarWindow(event)
  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: event.event_name,
    dates: `${start}/${end}`,
    details: description(event),
    ctz: CAMPUS_TIMEZONE,
  })
  if (event.location) params.set('location', event.location)
  return `https://calendar.google.com/calendar/render?${params}`
}

// ICS text values need these escaped or a comma in a room name breaks the field.
function escapeText(value) {
  return String(value)
    .replace(/\\/g, '\\\\')
    .replace(/\r?\n/g, '\\n')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
}

// Lines over 75 characters have to be folded, and every continuation starts with a space.
function fold(line) {
  const parts = []
  for (let i = 0; i < line.length; i += 74) {
    parts.push(line.slice(i, i + 74))
  }
  return parts.join('\r\n ')
}

export function buildIcs(event, now = new Date()) {
  const { allDay, start, end } = calendarWindow(event)

  // No TZID on purpose. A floating time shows at 5:00 PM on whatever calendar opens it,
  // which is right for people on campus and avoids shipping a VTIMEZONE block.
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//onCamp//Events//EN',
    'CALSCALE:GREGORIAN',
    'BEGIN:VEVENT',
    `UID:${event.event_id}@oncamp`,
    `DTSTAMP:${stamp(now, true)}Z`,
    allDay ? `DTSTART;VALUE=DATE:${start}` : `DTSTART:${start}`,
    allDay ? `DTEND;VALUE=DATE:${end}` : `DTEND:${end}`,
    `SUMMARY:${escapeText(event.event_name)}`,
    `DESCRIPTION:${escapeText(description(event))}`,
  ]
  if (event.location) lines.push(`LOCATION:${escapeText(event.location)}`)
  if (event.post_link) lines.push(`URL:${event.post_link}`)
  lines.push('END:VEVENT', 'END:VCALENDAR')

  return lines.map(fold).join('\r\n') + '\r\n'
}

export function downloadIcs(event) {
  const blob = new Blob([buildIcs(event)], { type: 'text/calendar;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${event.event_name.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.ics`
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}