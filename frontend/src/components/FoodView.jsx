import EventTile from './EventTile'

export default function FoodView({ events, weekCount, live, now, onOpen }) {
  const count = live ? weekCount : events.length
  const where = live ? 'coming up this week' : 'in this view'
  return (
    <section aria-label="Free food events">
      <p className="food-banner">
        {count > 0 ? <><strong>{count}</strong> free food {count === 1 ? 'event' : 'events'} {where}</> : `No free food events ${where}`}
      </p>
      {events.map((event) => <EventTile key={event.event_id} event={event} now={now} onOpen={onOpen} />)}
    </section>
  )
}
