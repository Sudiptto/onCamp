export function toISODate(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function monthMatrix(year, month) {
  const first = new Date(year, month, 1)
  const start = new Date(year, month, 1 - first.getDay())
  const weeks = []

  for (let week = 0; week < 6; week += 1) {
    weeks.push(
      Array.from({ length: 7 }, (_, day) => {
        const date = new Date(start)
        date.setDate(start.getDate() + week * 7 + day)
        return date
      }),
    )
  }

  const lastWeek = weeks[weeks.length - 1]
  if (lastWeek.every((date) => date.getMonth() !== month)) {
    weeks.pop()
  }
  return weeks
}

export function monthLabel(year, month) {
  return new Date(year, month, 1).toLocaleDateString('en-US', {
    month: 'long',
    year: 'numeric',
  })
}

export function formatLongDate(iso) {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  })
}

export function formatTime(value) {
  const [hourValue, minute] = value.split(':').map(Number)
  const suffix = hourValue >= 12 ? 'PM' : 'AM'
  const hour = hourValue % 12 || 12
  return `${hour}:${String(minute).padStart(2, '0')} ${suffix}`
}

export function formatTimeRange(start, end) {
  return `${formatTime(start)} – ${formatTime(end)}`
}

export function closestDate(events, today) {
  if (!events.length) return today
  return events.reduce((best, event) => {
    const bestDistance = Math.abs(Date.parse(best) - Date.parse(today))
    const distance = Math.abs(Date.parse(event.date) - Date.parse(today))
    return distance < bestDistance ? event.date : best
  }, events[0].date)
}
