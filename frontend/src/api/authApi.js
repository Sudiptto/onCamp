const SESSION_KEY = 'oncamp.session'
const ACCOUNTS_KEY = 'oncamp.accounts'

function readAccounts() {
  try {
    return JSON.parse(localStorage.getItem(ACCOUNTS_KEY) || '[]')
  } catch {
    return []
  }
}

function readSession() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function writeSession(session) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
  return session
}

export async function register({ name, email, password }) {
  const trimmedEmail = email.trim().toLowerCase()
  const trimmedName = name.trim()
  if (!trimmedName || !trimmedEmail || !password) {
    throw new Error('Name, email, and password are required.')
  }
  if (password.length < 6) {
    throw new Error('Password must be at least 6 characters.')
  }

  // TODO: replace this demo store with POST /api/auth/register
  // const response = await fetch('/api/auth/register', {
  //   method: 'POST',
  //   headers: { 'Content-Type': 'application/json' },
  //   body: JSON.stringify({ name: trimmedName, email: trimmedEmail, password }),
  // })
  const accounts = readAccounts()
  if (accounts.some((account) => account.email === trimmedEmail)) {
    throw new Error('An account with that email already exists.')
  }
  accounts.push({ name: trimmedName, email: trimmedEmail, password })
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts))

  return writeSession({ name: trimmedName, email: trimmedEmail })
}

export async function login({ email, password }) {
  const trimmedEmail = email.trim().toLowerCase()
  if (!trimmedEmail || !password) {
    throw new Error('Email and password are required.')
  }

  // TODO: replace this demo check with POST /api/auth/login
  // const response = await fetch('/api/auth/login', {
  //   method: 'POST',
  //   headers: { 'Content-Type': 'application/json' },
  //   body: JSON.stringify({ email: trimmedEmail, password }),
  // })
  const account = readAccounts().find(
    (item) => item.email === trimmedEmail && item.password === password,
  )
  if (!account) {
    throw new Error('Email or password is incorrect.')
  }

  return writeSession({ name: account.name, email: account.email })
}

export async function logout() {
  // TODO: POST /api/auth/logout
  // await fetch('/api/auth/logout', { method: 'POST' })
  sessionStorage.removeItem(SESSION_KEY)
}

export async function me() {
  // TODO: GET /api/auth/me
  // const response = await fetch('/api/auth/me')
  return readSession()
}
