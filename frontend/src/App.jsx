const events = [
  {
    title: 'Club Fair Night',
    time: 'Wed, Sept 25 • 6:00 PM',
    location: 'Hunter East Building',
    tag: 'Food',
  },
  {
    title: 'Design Meetup',
    time: 'Thu, Sept 26 • 5:30 PM',
    location: 'North Hall',
    tag: 'Event',
  },
  {
    title: 'Study Break Lounge',
    time: 'Fri, Sept 27 • 12:00 PM',
    location: 'Student Center',
    tag: 'Free food',
  },
]

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Hunter • campus discovery</p>
          <h1>onCamp</h1>
        </div>
        <button type="button" className="primary-button">
          View this week
        </button>
      </header>

      <main className="content">
        <section className="summary-card">
          <div>
            <p className="label">Discovery status</p>
            <h2>Connected to Hunter club activity</h2>
          </div>
          <span className="status-pill">Live pipeline</span>
        </section>

        <section className="event-list">
          {events.map((event) => (
            <article key={event.title} className="event-card">
              <div className="event-meta">
                <span className="event-tag">{event.tag}</span>
              </div>
              <h3>{event.title}</h3>
              <p>{event.time}</p>
              <p>{event.location}</p>
            </article>
          ))}
        </section>
      </main>
    </div>
  )
}
