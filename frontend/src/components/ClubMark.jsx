import { useState } from 'react'

function initials(name) {
  return name
    .split(' ')
    .filter((part) => part && part[0] === part[0].toUpperCase())
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
}

export default function ClubMark({ name, src }) {
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
