import { useEffect, useMemo, useRef, useState } from 'react'

import { fetchClubOptions, fetchEvents, fetchStats } from './api'
import AccountMenu from './components/auth/AccountMenu'
import AuthForm from './components/auth/AuthForm'
import { downloadIcs, googleCalendarUrl } from './calendar'
import { useAuth } from './context/AuthContext'
import { listSaved, toggleSaved } from './savedEvents'
import {
  closestDate,
  formatLongDate,
  formatTimeRange,
  monthLabel,
  monthMatrix,
  relativeDayLabel,
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

function EventCard({ event, today, selected, saved, onSelect, onToggleSave }) {
  return (
    <article className={selected ? 'event-card is-selected' : 'event-card'}>
      <button type="button" className="event-select" onClick={() => onSelect(event.date)}>
        <ClubMark name={event.club_name} src={event.club_pfp} />
        <span>
          <span className="event-kicker">
            {formatLongDate(event.date)}
            <span className="when-badge">{relativeDayLabel(event.date, today)}</span>
            {event.free_food && <span className="food-badge">Free food</span>}
          </span>
          <strong>{event.event_name}</strong>
          <span className="event-when">{formatTimeRange(event.start_time, event.end_time)}</span>
          <span className="event-where">{event.location || 'Location not specified'}</span>
        </span>
      </button>
      <div className="event-links">
        <a href={event.club_link} target="_blank" rel="noreferrer">
          {event.club_name}
        </a>
        {event.post_link && (
          <a href={event.post_link} target="_blank" rel="noreferrer">
            Post
          </a>
        )}
        {event.event_link && (
          <a href={event.event_link} target="_blank" rel="noreferrer">
            Sign up
          </a>
        )}
        <a href={googleCalendarUrl(event)} target="_blank" rel="noreferrer">
          Google Calendar
        </a>
        <button type="button" className="link-button" onClick={() => downloadIcs(event)}>
          .ics
        </button>
        {event.id != null && (
          <button
            type="button"
            className={saved ? 'save-button is-saved' : 'save-button'}
            aria-pressed={saved}
            onClick={() => onToggleSave(event)}
          >
            {saved ? 'Saved' : 'Save'}
          </button>
        )}
      </div>
    </article>
  )
}

const formatCount = (n) => (n >= 1000 ? `${n / 1000}K+` : `${n}+`)

export default function App() {
  const today = toISODate(new Date())
  const [mode, setMode] = useState('upcoming')
  const [range, setRange] = useState('2w')
  const [clubId, setClubId] = useState('')
  const [clubs, setClubs] = useState([])
  const [clubsError, setClubsError] = useState('')
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [cursor, setCursor] = useState(() => {
    const now = new Date()
    return { year: now.getFullYear(), month: now.getMonth() }
  })
  const [selected, setSelected] = useState(today)
  const [foodOnly, setFoodOnly] = useState(false)
  const [savedEvents, setSavedEvents] = useState([])
  const [savedOnly, setSavedOnly] = useState(false)
  const [saveError, setSaveError] = useState('')
  const savedOnlyRef = useRef(false)
  savedOnlyRef.current = savedOnly
  const { user, authLoading } = useAuth()
  const [stats, setStats] = useState(null)
  useEffect(() => {
    fetchStats().then(setStats).catch(() => {})  // the counter is optional, so ignore errors
  }, [])
  const [authFormOpen, setAuthFormOpen] = useState(false)
  const [authPrompt, setAuthPrompt] = useState('')

  function openSignIn(message = '') {
    setAuthPrompt(message)
    setAuthFormOpen(true)
  }

  // Archive and Saved both need an account. Drop back to the public calendar on sign-out.
  useEffect(() => {
    if (authLoading || user) return
    setSavedOnly(false)
    setSavedEvents([])
    setSaveError('')
    if (mode === 'archive') setMode('upcoming')
  }, [authLoading, user, mode])

  useEffect(() => {
    if (!user) return undefined
    let cancelled = false
    listSaved()
      .then((events) => {
        if (!cancelled) setSavedEvents(events)
      })
      .catch((err) => {
        if (!cancelled) setSaveError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [user])

  useEffect(() => {
    if (authLoading) return undefined
    let cancelled = false
    setClubsError('')
    fetchClubOptions({ includeArchive: Boolean(user) })
      .then((list) => {
        if (!cancelled) setClubs(list)
      })
      .catch((err) => {
        if (!cancelled) {
          setClubs([])
          setClubsError(`Could not load club filters: ${err.message}`)
        }
      })
    return () => {
      cancelled = true
    }
  }, [authLoading, user?.id])

  useEffect(() => {
    if (authLoading) return undefined
    let cancelled = false
    setLoading(true)
    setError('')
    fetchEvents({ mode, range, clubId })
      .then((data) => {
        if (cancelled) return
        setPayload(data)
        if (savedOnlyRef.current) return
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
  }, [mode, range, clubId, today, authLoading, user?.id])

  const allEvents = payload?.events ?? []
  const savedIds = useMemo(
    () => new Set(savedEvents.map((event) => event.event_id)),
    [savedEvents],
  )
  const sourceEvents = savedOnly ? savedEvents : allEvents
  const events = sourceEvents.filter((event) => {
    if (foodOnly && !event.free_food) return false
    if (savedOnly && clubId && event.club_id !== clubId) return false
    return true
  })
  const foodCount = allEvents.filter((event) => event.free_food).length
  const byDate = useMemo(() => {
    const grouped = new Map()
    for (const event of events) {
      const dayEvents = grouped.get(event.date) ?? []
      dayEvents.push(event)
      grouped.set(event.date, dayEvents)
    }
    return grouped
  }, [events])
  const scheduleDays = useMemo(
    () => [...byDate.keys()].sort().map((date) => ({ date, events: byDate.get(date) })),
    [byDate],
  )

  const weeks = monthMatrix(cursor.year, cursor.month)

  function focusDate(iso) {
    const [year, month] = iso.split('-').map(Number)
    setSelected(iso)
    setCursor({ year, month: month - 1 })
  }

  function toggleSavedView() {
    if (!user) {
      openSignIn('Sign in with Google to save events and see them here.')
      return
    }
    const next = !savedOnly
    setSavedOnly(next)
    if (!next) return
    const visible = savedEvents.filter((event) => {
      if (foodOnly && !event.free_food) return false
      if (clubId && event.club_id !== clubId) return false
      return true
    })
    if (visible.length) focusDate(closestDate(visible, today))
  }

  async function onToggleSave(event) {
    if (!user) {
      openSignIn('Sign in with Google to save this event.')
      return
    }
    if (event.id == null) return
    setSaveError('')
    try {
      setSavedEvents(await toggleSaved(event, savedIds.has(event.event_id)))
    } catch (err) {
      setSaveError(err.message)
    }
  }

  function toggleFood() {
    const next = !foodOnly
    setFoodOnly(next)
    if (!next) return
    const foodEvents = (payload?.events ?? []).filter((event) => event.free_food)
    if (foodEvents.length) focusDate(closestDate(foodEvents, today))
  }

  function shiftMonth(offset) {
    const next = new Date(cursor.year, cursor.month + offset, 1)
    setCursor({ year: next.getFullYear(), month: next.getMonth() })
  }

  const viewLabel = savedOnly
    ? 'Saved'
    : mode === 'archive'
      ? 'Past semester'
      : RANGES.find((item) => item.id === range)?.label

  return (
    <div className="page">
      <header className="masthead">
        <div className="masthead-inner">
          <p className="eyebrow">Hunter College</p>
          <h1>onCamp</h1>
          <p className="lede">Club events, in one calendar.</p>
          {stats?.clubs > 0 && (
            <ul className="site-stats" aria-label="onCamp at a glance">
              <li><strong>{stats.clubs}</strong> clubs</li>
              <li><strong>{stats.upcoming_events}</strong> upcoming events</li>
              {stats.users_milestone && (
                <li><strong>{formatCount(stats.users_milestone)}</strong> people signed in</li>
              )}
            </ul>
          )}
          <div className="masthead-account">
            <AccountMenu onSignIn={() => openSignIn()} />
          </div>
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
              onClick={() => (user ? setMode('archive') : openSignIn('Sign in with Google to browse past events.'))}
            >
              Archive
            </button>
            <button type="button" aria-pressed={foodOnly} onClick={toggleFood}>
              Free food
            </button>
            <button type="button" aria-pressed={savedOnly} onClick={toggleSavedView}>
              Saved{user && savedEvents.length ? ` ${savedEvents.length}` : ''}
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
          {!loading && !error && `${events.length} ${events.length === 1 ? 'event' : 'events'} · ${viewLabel}${!savedOnly && foodCount && !foodOnly ? ` · ${foodCount} with free food` : ''}${user && savedEvents.length && !savedOnly ? ` · ${savedEvents.length} saved` : ''}`}
        </p>
        {clubsError && <p className="status-line" role="alert">{clubsError}</p>}

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
                    const hasFood = dayEvents.some((event) => event.free_food)
                    const hasSaved = dayEvents.some((event) => savedIds.has(event.event_id))
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
                          hasFood ? 'has-food' : '',
                          hasSaved ? 'has-saved' : '',
                        ].filter(Boolean).join(' ')}
                        aria-pressed={iso === selected}
                        aria-label={`${formatLongDate(iso)}, ${dayEvents.length} events${hasFood ? ', free food' : ''}${hasSaved ? ', saved' : ''}`}
                        onClick={() => focusDate(iso)}
                      >
                        <span className="day-top">
                          <span className="day-number">{date.getDate()}</span>
                        </span>
                        {dayEvents.length > 0 && (
                          <span className={hasFood ? 'day-dot is-food' : 'day-dot'} aria-hidden="true" />
                        )}
                        <span className="day-chips">
                          {dayEvents.slice(0, 2).map((event) => (
                            <span key={event.event_id} className={event.free_food ? 'day-chip is-food' : 'day-chip'}>
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
            <h2>{savedOnly ? 'Saved' : mode === 'archive' ? 'Archive' : 'Schedule'}</h2>
            {payload?.limited && !savedOnly && (
              <div className="unlock-banner" role="note">
                <span>
                  {payload.locked_count} more event{payload.locked_count === 1 ? '' : 's'} later on.
                </span>
                <button type="button" onClick={() => openSignIn('Sign in with Google to see every upcoming event.')}>
                  Sign in to see them
                </button>
              </div>
            )}
            {saveError && <p className="empty" role="alert">{saveError}</p>}
            {!loading && !error && events.length === 0 && (
              <p className="empty">
                {savedOnly
                  ? 'No saved events yet.'
                  : foodOnly
                    ? 'No free food in this view.'
                    : 'No events in this view.'}
              </p>
            )}
            <div className="schedule-list">
              {scheduleDays.map((day) => (
                <section key={day.date} className="schedule-day" aria-label={formatLongDate(day.date)}>
                  <h3>{formatLongDate(day.date)}</h3>
                  {day.events.map((event) => (
                    <EventCard
                      key={event.event_id}
                      event={event}
                      today={today}
                      selected={event.date === selected}
                      saved={savedIds.has(event.event_id)}
                      onSelect={focusDate}
                      onToggleSave={onToggleSave}
                    />
                  ))}
                </section>
              ))}
            </div>
          </section>
        </div>
      </main>
      {authFormOpen && <AuthForm message={authPrompt} onClose={() => setAuthFormOpen(false)} />}
    </div>
  )
}
