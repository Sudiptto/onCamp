import { QUICK_FILTERS } from '../filters.js'

export default function QuickFilters({ value, onChange }) {
  return (
    <div className="quick-filters" role="group" aria-label="Quick filters">
      {QUICK_FILTERS.map((filter) => (
        <button key={filter.id} type="button" className="chip" aria-pressed={value === filter.id} onClick={() => onChange(filter.id)}>
          {filter.id === 'food' && <span className="chip-dot" aria-hidden="true" />}
          {filter.label}
        </button>
      ))}
    </div>
  )
}
