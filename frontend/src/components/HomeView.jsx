import { formatLongDate, formatTimeRange, toISODate } from '../dates'
import { groupByDate, hasClockTime, pickFeatured, whenLabel } from '../filters.js'
import ClubMark from './ClubMark'
import EventTile from './EventTile'

// `live` is the normal upcoming view. Archive and Saved skip the "happening today" card.
export default function HomeView({ events, now, live, title, onOpen }) {
  const today = toISODate(now)
  const featured = live ? pickFeatured(events, now) : null
  const todayCount = live ? events.filter((event) => event.date === today).length : 0
  const rest = featured ? events.filter((event) => event !== featured) : events

  const days = groupByDate(rest)

  return (
    <>
      {featured && (
        <section aria-labelledby="today-heading">
          <div className="section-head">
            <h2 id="today-heading">Happening today</h2>
            <span>{todayCount} {todayCount === 1 ? 'event' : 'events'}</span>
          </div>
          <button type="button" className="hero" onClick={() => onOpen(featured)}>
            <span className="hero-top">
              <ClubMark name={featured.club_name} src={featured.club_pfp} />
              <span className="hero-club">{featured.club_name}</span>
              {featured.free_food && <span className="food-pill">Free food</span>}
            </span>
            <span className="hero-title">{featured.event_name}</span>
            <span className="hero-when">{whenLabel(featured, now)}{hasClockTime(featured) && ` · ${formatTimeRange(featured.start_time, featured.end_time)}`}</span>
            <span className="hero-where">{featured.location || 'Location not specified'}</span>
          </button>
        </section>
      )}

      {days.length > 0 && (
        <section aria-labelledby="upcoming-heading">
          <div className="section-head"><h2 id="upcoming-heading">{title}</h2></div>
          {days.map((day) => (
            <div key={day.date} className="home-day">
              <h3>{formatLongDate(day.date)}</h3>
              {day.events.map((event) => <EventTile key={event.event_id} event={event} now={now} onOpen={onOpen} />)}
            </div>
          ))}
        </section>
      )}
    </>
  )
}
