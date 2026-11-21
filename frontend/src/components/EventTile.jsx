import { whenLabel } from '../filters.js'
import ClubMark from './ClubMark'

export default function EventTile({ event, now, onOpen }) {
  const when = whenLabel(event, now)
  const soon = when.startsWith('Starting') || when === 'Happening now'
  return (
    <button type="button" className="tile" onClick={() => onOpen(event)}>
      <span className="tile-head">
        <ClubMark name={event.club_name} src={event.club_pfp} />
        <span className="tile-club">
          <span className="tile-club-name">{event.club_name}</span>
          <span className={soon ? 'tile-when is-soon' : 'tile-when'}>{when}</span>
        </span>
        {event.free_food && <span className="food-pill">Free food</span>}
      </span>
      <strong className="tile-title">{event.event_name}</strong>
      <span className="tile-where">{event.location || 'Location not specified'}</span>
    </button>
  )
}
