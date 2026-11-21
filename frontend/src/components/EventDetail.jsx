import { useEffect, useRef } from 'react'

import { downloadIcs, googleCalendarUrl } from '../calendar'
import { formatLongDate, formatTimeRange } from '../dates'
import { hasClockTime, instagramHandle } from '../filters.js'
import ClubMark from './ClubMark'
import EventTile from './EventTile'

// bottom sheet on phones, centered card on desktop. Escape or tapping outside closes it
export default function EventDetail({ event, now, saved, related, onClose, onToggleSave, onOpen }) {
  const closeRef = useRef(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (key) => key.key === 'Escape' && onCloseRef.current()
    document.addEventListener('keydown', onKey)
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previousOverflow
    }
  }, [])

  const handle = instagramHandle(event.club_link)

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <section className="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title" onClick={(click) => click.stopPropagation()}>
        <button ref={closeRef} type="button" className="sheet-close" aria-label="Close" onClick={onClose}>×</button>

        <div className="sheet-club">
          <ClubMark name={event.club_name} src={event.club_pfp} />
          <span>
            <a href={event.club_link} target="_blank" rel="noreferrer">{event.club_name}</a>
            {handle && <span className="sheet-handle">@{handle}</span>}
          </span>
        </div>

        <h2 id="sheet-title">{event.event_name}</h2>
        {event.free_food && <p className="food-pill is-large">Free food</p>}

        <dl className="sheet-facts">
          <div>
            <dt>When</dt>
            <dd>{formatLongDate(event.date)}<span>{hasClockTime(event) ? formatTimeRange(event.start_time, event.end_time) : 'Time not specified'}</span></dd>
          </div>
          <div>
            <dt>Where</dt>
            <dd>{event.location || 'Location not specified'}<span>Hunter College</span></dd>
          </div>
        </dl>

        {event.post_link && (
          <p className="ai-note">
            <span>Detected by AI from {handle ? <strong>@{handle}</strong> : 'the club'}'s Instagram post</span>
            <a href={event.post_link} target="_blank" rel="noreferrer">View original post ↗</a>
          </p>
        )}

        <div className="sheet-actions">
          <a className="btn btn-primary" href={googleCalendarUrl(event)} target="_blank" rel="noreferrer">Add to Google Calendar</a>
          <button type="button" className="btn" onClick={() => downloadIcs(event)}>Download .ics</button>
          {event.id != null && (
            <button type="button" className={saved ? 'btn is-saved' : 'btn'} aria-pressed={saved} onClick={() => onToggleSave(event)}>
              {saved ? 'Saved' : 'Save'}
            </button>
          )}
          {event.event_link && <a className="btn" href={event.event_link} target="_blank" rel="noreferrer">Sign up</a>}
        </div>

        <h3>More from this club</h3>
        {related.length > 0
          ? related.map((other) => <EventTile key={other.event_id} event={other} now={now} onOpen={onOpen} />)
          : <p className="empty">No other upcoming events from this club right now.</p>}
      </section>
    </div>
  )
}
