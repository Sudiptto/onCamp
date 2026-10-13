import { useEffect, useMemo, useState } from 'react'

import { fetchClubOptions, fetchEvents } from './api'
import {
  closestDate,
  formatLongDate,
  formatTimeRange,
  monthLabel,
  monthMatrix,
  toISODate,
} from './dates'

const RANGES = [
  { id: '1w', label: '1 week' },
  { id: '2w', label: '2 weeks' },
  { id: '1m', label: '1 month' },
  { id: 'semester', label: 'Semester' },
  { id: 'all', label: 'All' },
]

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function initials(name) {
  return name
    .split(' ')
    .filter((part) => part && part[0] === part[0].toUpperCase())
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
}

function ClubMark({ name, src }) {
  const [failed, setFailed] = useState(false)
  if (failed || !src) {
    return <span className="avatar fallback">{initials(name)}</span>
  }
  return (
    <img
      className="avatar"
      src={src}
      alt=""
      onError={() => setFailed(true)}
    />
  )
}

function EventCard({ event, selected, onSelect }) {
  return (
    <article className={selected ? 'event-card is-selected' : 'event-card'}>
      <button type="button" className="event-select" onClick={() => onSelect(event.date)}>
        <ClubMark name={event.club_name} src={event.club_pfp} />
        <span>
          <span className="event-kicker">{formatLongDate(event.date)}</span>
          <strong>{event.event_name}</strong>
          <span className="event-when">{formatTimeRange(event.start_time, event.end_time)}</span>
          <span className="event-where">{event.location}</span>
        </span>
      </button>
      <div className="event-links">
        <a href={event.club_link} target="_blank" rel="noreferrer">
          {event.club_name}
        </a>
        <a href={event.post_link} target="_blank" rel="noreferrer">
          Post
        </a>
        {event.event_link && (
          <a href={event.event_link} target="_blank" rel="noreferrer">
            Sign up
          </a>
        )}
      </div>
    </article>
  )
}

export default function App() {
  const today = toISODate(new Date())
  const [mode, setMode] = useState('upcoming')
  const [range, setRange] = useState('2w')
  const [clubId, setClubId] = useState('')
  const [clubs, setClubs] = useState([])
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [cursor, setCursor] = useState(() => {
    const now = new Date()
    return { year: now.getFullYear(), month: now.getMonth() }
  })
  const [selected, setSelected] = useState(today)

  useEffect(() => {
    let cancelled = false
    fetchClubOptions()
      .then((list) => {
        if (!cancelled) setClubs(list)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    fetchEvents({ mode, range, clubId })
      .then((data) => {
        if (cancelled) return
        setPayload(data)
        const focus = closestDate(data.events, today)
        const [year, month] = focus.split('-').map(Number)
        setCursor({ year, month: month - 1 })
        setSelected(focus)
      })
      .catch((err) => {
        if (!cancelled) {
          setPayload(null)
          setError(err.message)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [mode, range, clubId, today])

  const events = payload?.events ?? []
  const byDate = useMemo(() => {
    const grouped = new Map()
    for (const event of events) {
      const dayEvents = grouped.get(event.date) ?? []
      dayEvents.push(event)
      grouped.set(event.date, dayEvents)
    }
    return grouped
  }, [events])

  const weeks = monthMatrix(cursor.year, cursor.month)

  function focusDate(iso) {
    const [year, month] = iso.split('-').map(Number)
    setSelected(iso)
    setCursor({ year, month: month - 1 })
  }

  function shiftMonth(offset) {
    const next = new Date(cursor.year, cursor.month + offset, 1)
    setCursor({ year: next.getFullYear(), month: next.getMonth() })
  }

  const viewLabel = mode === 'archive' ? 'Past semester' : RANGES.find((item) => item.id === range)?.label

  return (
    <div className="page">
      <header className="masthead">
        <div className="masthead-inner">
          <p className="eyebrow">Hunter College</p>
          <h1>onCamp</h1>
          <p className="lede">Club events, in one calendar.</p>
        </div>
      </header>

      <main className="shell">
        <section className="toolbar" aria-label="Event filters">
          <div className="mode-switch" role="group" aria-label="Which events">
            <button
              type="button"
              aria-pressed={mode === 'upcoming'}
              onClick={() => setMode('upcoming')}
            >
              Upcoming
            </button>
            <button
              type="button"
              aria-pressed={mode === 'archive'}
              onClick={() => setMode('archive')}
            >
              Archive
            </button>
          </div>

          {mode === 'upcoming' && (
            <div className="range-switch" role="group" aria-label="Time range">
              {RANGES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  aria-pressed={range === item.id}
                  onClick={() => setRange(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}

          <label className="club-filter">
            Club
            <select value={clubId} onChange={(event) => setClubId(event.target.value)}>
              <option value="">All clubs</option>
              {clubs.map((club) => (
                <option key={club.id} value={club.id}>
                  {club.name}
                </option>
              ))}
            </select>
          </label>
        </section>

        <p className="status-line">
          {loading && 'Loading events…'}
          {!loading && error && error}
          {!loading && !error && `${payload?.count ?? 0} ${payload?.count === 1 ? 'event' : 'events'} · ${viewLabel}`}
        </p>

        <div className="layout">
          <section className="calendar" aria-label="Month calendar">
            <div className="calendar-nav">
              <button type="button" onClick={() => shiftMonth(-1)} aria-label="Previous month">
                ‹
              </button>
              <h2>{monthLabel(cursor.year, cursor.month)}</h2>
              <button type="button" onClick={() => shiftMonth(1)} aria-label="Next month">
                ›
              </button>
              <button type="button" className="today-button" onClick={() => focusDate(today)}>
                Today
              </button>
            </div>

            <div className="weekday-row">
              {WEEKDAYS.map((day) => (
                <span key={day}>{day}</span>
              ))}
            </div>

            <div className="weeks">
              {weeks.map((week) => (
                <div key={toISODate(week[0])} className="week">
                  {week.map((date) => {
                    const iso = toISODate(date)
                    const dayEvents = byDate.get(iso) ?? []
                    const outside = date.getMonth() !== cursor.month
                    return (
                      <button
                        key={iso}
                        type="button"
                        className={[
                          'day',
                          outside ? 'is-outside' : '',
                          iso === today ? 'is-today' : '',
                          iso === selected ? 'is-selected' : '',
                        ].filter(Boolean).join(' ')}
                        aria-pressed={iso === selected}
                        aria-label={`${formatLongDate(iso)}, ${dayEvents.length} events`}
                        onClick={() => focusDate(iso)}
                      >
                        <span className="day-number">{date.getDate()}</span>
                        {dayEvents.length > 0 && <span className="day-dot" aria-hidden="true" />}
                        <span className="day-chips">
                          {dayEvents.slice(0, 2).map((event) => (
                            <span key={event.event_id} className="day-chip">
                              {event.event_name}
                            </span>
                          ))}
                          {dayEvents.length > 2 && (
                            <span className="day-more">+{dayEvents.length - 2}</span>
                          )}
                        </span>
                      </button>
                    )
                  })}
                </div>
              ))}
            </div>
          </section>

          <section className="schedule" aria-label="Events in this view">
            <h2>{mode === 'archive' ? 'Archive' : 'Schedule'}</h2>
            {!loading && !error && events.length === 0 && (
              <p className="empty">No events in this view.</p>
            )}
            <div className="schedule-list">
              {events.map((event) => (
                <EventCard
                  key={event.event_id}
                  event={event}
                  selected={event.date === selected}
                  onSelect={focusDate}
                />
              ))}
            </div>
          </section>
        </div>
      </main>
    </div>
  )
}
