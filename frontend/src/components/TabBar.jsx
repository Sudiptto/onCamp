// bottom bar on phones, under the header on desktop (the CSS handles which)
const TABS = [
  { id: 'home', label: 'Home', icon: <path d="M3 11l9-8 9 8v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z" /> },
  { id: 'calendar', label: 'Calendar', icon: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></> },
  { id: 'food', label: 'Food', icon: <path d="M6 3v7a2 2 0 0 0 4 0V3M8 12v9M17 3c-2 2-3 5-3 8h3v10" /> },
  { id: 'clubs', label: 'Clubs', icon: <><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c.6-3.5 3.3-5.5 6.5-5.5s5.9 2 6.5 5.5" /><circle cx="17" cy="9" r="2.5" /><path d="M17.5 14.5c2.3.3 3.9 1.9 4.5 4.5" /></> },
]

export default function TabBar({ active, onChange }) {
  return (
    <nav className="tab-bar" aria-label="Sections">
      {TABS.map((tab) => (
        <button key={tab.id} type="button" className={active === tab.id ? 'tab is-active' : 'tab'} aria-current={active === tab.id ? 'page' : undefined} onClick={() => onChange(tab.id)}>
          <svg viewBox="0 0 24 24" aria-hidden="true">{tab.icon}</svg>
          <span>{tab.label}</span>
        </button>
      ))}
    </nav>
  )
}
