import ClubMark from './ClubMark'

// only clubs that have posted events show up, that's all the API knows about right now
export default function ClubsView({ clubs, onPick }) {
  const withEvents = clubs.filter((club) => club.upcoming > 0).length
  return (
    <section aria-label="Clubs">
      <div className="club-intro">
        <h2>Clubs with events</h2>
        <p>Pick a club to see what it has coming up.</p>
        <ul className="site-stats">
          <li><strong>{clubs.length}</strong> clubs</li>
          <li><strong>{withEvents}</strong> with upcoming events</li>
        </ul>
      </div>
      {clubs.length === 0 ? <p className="empty">No clubs to show yet.</p> : (
        <ul className="club-list">
          {clubs.map((club) => (
            <li key={club.id}>
              <button type="button" className="club-row" onClick={() => onPick(club.id)}>
                <ClubMark name={club.name} src={club.pfp} />
                <span className="club-row-text">
                  <strong>{club.name}</strong>
                  {club.handle && <span className="club-handle">@{club.handle}</span>}
                  <span className="club-count">{club.upcoming > 0 ? `${club.upcoming} upcoming` : 'No upcoming events'}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
