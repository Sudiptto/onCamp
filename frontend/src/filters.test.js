import assert from 'node:assert/strict'
import test from 'node:test'

import {
  countFoodThisWeek,
  formatClock,
  groupByDate,
  hasClockTime,
  instagramHandle,
  matchesQuickFilter,
  moreFromClub,
  pickFeatured,
  sameClub,
  sortEvents,
  summarizeClubs,
  whenLabel,
} from './filters.js'

// Wednesday, Nov 18 2026, 4:45 PM local time.
const NOW = new Date(2026, 10, 18, 16, 45)

const event = (overrides = {}) => ({
  event_id: 'e1',
  club_id: 1,
  club_name: 'Hunter Coding Club',
  event_name: 'Pizza Night',
  date: '2026-11-18',
  start_time: '17:30',
  end_time: null,
  free_food: false,
  ...overrides,
})

test('formats clock times without trailing :00', () => {
  assert.equal(formatClock('13:00'), '1 PM')
  assert.equal(formatClock('17:30'), '5:30 PM')
  assert.equal(formatClock('00:15'), '12:15 AM')
})

test('a midnight start with no end counts as no time', () => {
  assert.equal(hasClockTime({ start_time: '00:00', end_time: null }), false)
  assert.equal(hasClockTime({ start_time: '00:00', end_time: '01:00' }), true)
  assert.equal(hasClockTime({ start_time: null }), false)
})

test('quick filters: food, today, week', () => {
  assert.equal(matchesQuickFilter(event({ free_food: true }), 'food', NOW), true)
  assert.equal(matchesQuickFilter(event(), 'food', NOW), false)
  assert.equal(matchesQuickFilter(event(), 'today', NOW), true)
  assert.equal(matchesQuickFilter(event({ date: '2026-11-19' }), 'today', NOW), false)
  assert.equal(matchesQuickFilter(event({ date: '2026-11-24' }), 'week', NOW), true)
  assert.equal(matchesQuickFilter(event({ date: '2026-11-25' }), 'week', NOW), false)
  assert.equal(matchesQuickFilter(event({ date: '2026-11-17' }), 'week', NOW), false)
  assert.equal(matchesQuickFilter(event({ date: '2030-01-01' }), 'all', NOW), true)
})

test('tonight means today at 5 PM or later', () => {
  assert.equal(matchesQuickFilter(event({ start_time: '17:00' }), 'tonight', NOW), true)
  assert.equal(matchesQuickFilter(event({ start_time: '16:59' }), 'tonight', NOW), false)
  assert.equal(matchesQuickFilter(event({ start_time: '00:00' }), 'tonight', NOW), false)
  assert.equal(matchesQuickFilter(event({ date: '2026-11-19', start_time: '19:00' }), 'tonight', NOW), false)
})

test('sorts by date, then time', () => {
  const sorted = sortEvents([
    event({ event_id: 'c', date: '2026-11-19', start_time: '09:00' }),
    event({ event_id: 'b', start_time: '18:00' }),
    event({ event_id: 'a', start_time: '12:00' }),
  ])
  assert.deepEqual(sorted.map((item) => item.event_id), ['a', 'b', 'c'])
})

test('when labels', () => {
  assert.equal(whenLabel(event({ start_time: '17:30' }), NOW), 'Starting in 45 min')
  assert.equal(whenLabel(event({ start_time: '16:00', end_time: '17:00' }), NOW), 'Happening now')
  assert.equal(whenLabel(event({ start_time: '20:00' }), NOW), 'Today at 8 PM')
  assert.equal(whenLabel(event({ start_time: '09:00', end_time: '10:00' }), NOW), 'Earlier today at 9 AM')
  assert.equal(whenLabel(event({ start_time: '00:00' }), NOW), 'Today')
  assert.equal(whenLabel(event({ date: '2026-11-19', start_time: '13:00' }), NOW), 'Tomorrow at 1 PM')
  assert.equal(whenLabel(event({ date: '2026-11-21', start_time: '14:00' }), NOW), 'Saturday at 2 PM')
  assert.equal(whenLabel(event({ date: '2026-12-03', start_time: '18:00' }), NOW), 'Dec 3 at 6 PM')
})

test('featured event is the first one today that has not ended', () => {
  const finished = event({ event_id: 'done', start_time: '09:00', end_time: '10:00' })
  const upcoming = event({ event_id: 'next', start_time: '17:30' })
  const tomorrow = event({ event_id: 'later', date: '2026-11-19' })
  assert.equal(pickFeatured([finished, upcoming, tomorrow], NOW).event_id, 'next')
  assert.equal(pickFeatured([finished, tomorrow], NOW), null)
})

test('counts free food in the next seven days', () => {
  const events = [
    event({ free_food: true }),
    event({ free_food: true, date: '2026-11-24' }),
    event({ free_food: true, date: '2026-12-01' }),
    event({ free_food: false }),
  ]
  assert.equal(countFoodThisWeek(events, NOW), 2)
})

test('reads an Instagram handle from a profile link', () => {
  assert.equal(instagramHandle('https://www.instagram.com/huntercoding/'), 'huntercoding')
  assert.equal(instagramHandle(''), '')
  assert.equal(instagramHandle(undefined), '')
})

test('club summaries count upcoming events and sort busiest first', () => {
  const events = [
    event({ club_id: 2, club_pfp: 'b.png', club_link: 'https://www.instagram.com/beta/' }),
    event({ club_id: 2, date: '2026-11-20' }),
    event({ club_id: 2, date: '2026-11-01' }),
    event({ club_id: 1, club_link: 'https://www.instagram.com/alpha/' }),
  ]
  const clubs = [
    { id: 1, name: 'Alpha' },
    { id: 2, name: 'Beta' },
    { id: 3, name: 'Gamma' },
  ]
  const rows = summarizeClubs(events, clubs, '2026-11-18')
  assert.deepEqual(rows.map((row) => [row.name, row.upcoming]), [['Beta', 2], ['Alpha', 1], ['Gamma', 0]])
  assert.equal(rows[0].handle, 'beta')
  assert.equal(rows[0].pfp, 'b.png')
  assert.equal(rows[2].handle, '')
})

test('formats noon, midnight and the minutes in between', () => {
  assert.equal(formatClock('12:00'), '12 PM')
  assert.equal(formatClock('00:00'), '12 AM')
  assert.equal(formatClock('12:05'), '12:05 PM')
  assert.equal(formatClock('23:59'), '11:59 PM')
})

test('a start time of 00:00 only counts if the event has an end time', () => {
  assert.equal(hasClockTime({ start_time: '00:00', end_time: '00:30' }), true)
  assert.equal(hasClockTime({ start_time: '09:15', end_time: null }), true)
  assert.equal(hasClockTime({}), false)
})

test('this week covers today through six days out', () => {
  assert.equal(matchesQuickFilter(event({ date: '2026-11-18' }), 'week', NOW), true)
  assert.equal(matchesQuickFilter(event({ date: '2026-11-24' }), 'week', NOW), true)
  assert.equal(matchesQuickFilter(event({ date: '2026-11-25' }), 'week', NOW), false)
})

test('this week still works across a month and year boundary', () => {
  const lateDecember = new Date(2026, 11, 29, 10, 0)
  assert.equal(matchesQuickFilter(event({ date: '2027-01-04' }), 'week', lateDecember), true)
  assert.equal(matchesQuickFilter(event({ date: '2027-01-05' }), 'week', lateDecember), false)
})

test('tonight ignores events with no start time and keeps late ones', () => {
  assert.equal(matchesQuickFilter(event({ start_time: null }), 'tonight', NOW), false)
  assert.equal(matchesQuickFilter(event({ start_time: '23:30' }), 'tonight', NOW), true)
})

test('free food only goes by the free_food flag', () => {
  assert.equal(matchesQuickFilter(event({ free_food: undefined }), 'food', NOW), false)
  assert.equal(matchesQuickFilter(event({ free_food: 1 }), 'food', NOW), true)
})

test('an unknown filter id lets everything through', () => {
  assert.equal(matchesQuickFilter(event(), 'nope', NOW), true)
})

test('sorting does not touch the original list and puts untimed events first on their day', () => {
  const list = [event({ event_id: 'b', start_time: '09:00' }), event({ event_id: 'a', start_time: null })]
  const sorted = sortEvents(list)
  assert.deepEqual(sorted.map((item) => item.event_id), ['a', 'b'])
  assert.deepEqual(list.map((item) => item.event_id), ['b', 'a'])
})

test('starting-soon label switches to a clock time past 90 minutes', () => {
  const at = (hour, minute) => new Date(2026, 10, 18, hour, minute)
  assert.equal(whenLabel(event({ start_time: '18:30' }), at(17, 0)), 'Starting in 90 min')
  assert.equal(whenLabel(event({ start_time: '18:31' }), at(17, 0)), 'Today at 6:31 PM')
  assert.equal(whenLabel(event({ start_time: '17:01' }), at(17, 0)), 'Starting in 1 min')
})

test('an event is happening now from its start until its end', () => {
  const at = (hour, minute) => new Date(2026, 10, 18, hour, minute)
  const timed = event({ start_time: '17:00', end_time: '18:00' })
  assert.equal(whenLabel(timed, at(17, 0)), 'Happening now')
  assert.equal(whenLabel(timed, at(17, 59)), 'Happening now')
  assert.equal(whenLabel(timed, at(18, 0)), 'Earlier today at 5 PM')
})

test('an event with no end time is treated as an hour long', () => {
  const at = (hour, minute) => new Date(2026, 10, 18, hour, minute)
  const open = event({ start_time: '17:00', end_time: null })
  assert.equal(whenLabel(open, at(17, 59)), 'Happening now')
  assert.equal(whenLabel(open, at(18, 0)), 'Earlier today at 5 PM')
})

test('an end time before the start falls back to the one hour slot', () => {
  const backwards = event({ start_time: '22:00', end_time: '01:00' })
  assert.equal(whenLabel(backwards, new Date(2026, 10, 18, 22, 30)), 'Happening now')
  assert.equal(whenLabel(backwards, new Date(2026, 10, 18, 23, 5)), 'Earlier today at 10 PM')
})

test('when labels for days further out', () => {
  assert.equal(whenLabel(event({ date: '2026-11-24', start_time: '09:00' }), NOW), 'Tuesday at 9 AM')
  assert.equal(whenLabel(event({ date: '2026-11-25', start_time: '09:00' }), NOW), 'Nov 25 at 9 AM')
  assert.equal(whenLabel(event({ date: '2026-11-19', start_time: '00:00' }), NOW), 'Tomorrow')
  assert.equal(whenLabel(event({ date: '2026-12-25', start_time: null }), NOW), 'Dec 25')
})

test('a past date reads as a plain date', () => {
  assert.equal(whenLabel(event({ date: '2026-11-10', start_time: '12:00' }), NOW), 'Nov 10 at 12 PM')
})

test('featured event skips ones that already ended and keeps date-only ones', () => {
  const ended = event({ event_id: 'ended', start_time: '10:00', end_time: '11:00' })
  const dateOnly = event({ event_id: 'dateonly', start_time: '00:00', end_time: null })
  assert.equal(pickFeatured([ended, dateOnly], NOW).event_id, 'dateonly')
  assert.equal(pickFeatured([], NOW), null)
})

test('featured event is still the current one while it is running', () => {
  const running = event({ event_id: 'running', start_time: '16:00', end_time: '17:00' })
  const later = event({ event_id: 'later', start_time: '19:00' })
  assert.equal(pickFeatured([running, later], NOW).event_id, 'running')
})

test('food count ignores past days and non-food events', () => {
  const events = [
    event({ free_food: true, date: '2026-11-17' }),
    event({ free_food: true, date: '2026-11-18' }),
    event({ free_food: false, date: '2026-11-19' }),
  ]
  assert.equal(countFoodThisWeek(events, NOW), 1)
  assert.equal(countFoodThisWeek([], NOW), 0)
})

test('instagram handles with query strings, no trailing slash and odd casing', () => {
  assert.equal(instagramHandle('https://instagram.com/huntercoding'), 'huntercoding')
  assert.equal(instagramHandle('https://www.instagram.com/huntercoding/?hl=en'), 'huntercoding')
  assert.equal(instagramHandle('HTTPS://WWW.INSTAGRAM.COM/Hunter_Coding.Club/'), 'Hunter_Coding.Club')
  assert.equal(instagramHandle('https://example.com/huntercoding'), '')
  assert.equal(instagramHandle(null), '')
})

test('club summaries handle clubs with no events and events from unlisted clubs', () => {
  const rows = summarizeClubs([event({ club_id: 99 })], [{ id: 1, name: 'Alpha' }], '2026-11-18')
  assert.equal(rows.length, 1)
  assert.deepEqual(rows[0], { id: 1, name: 'Alpha', pfp: '', handle: '', upcoming: 0 })
  assert.deepEqual(summarizeClubs([], [], '2026-11-18'), [])
})

test('club summaries count today as upcoming and break ties by name', () => {
  const events = [event({ club_id: 1, date: '2026-11-18' }), event({ club_id: 2, date: '2026-11-18' })]
  const rows = summarizeClubs(events, [{ id: 2, name: 'Zeta' }, { id: 1, name: 'Alpha' }], '2026-11-18')
  assert.deepEqual(rows.map((row) => [row.name, row.upcoming]), [['Alpha', 1], ['Zeta', 1]])
})

test('grouping puts neighbors with the same date together and keeps the order', () => {
  const days = groupByDate([
    event({ event_id: 'a', date: '2026-11-18' }),
    event({ event_id: 'b', date: '2026-11-18' }),
    event({ event_id: 'c', date: '2026-11-19' }),
    event({ event_id: 'd', date: '2026-11-20' }),
  ])
  assert.deepEqual(days.map((day) => [day.date, day.events.map((item) => item.event_id)]), [
    ['2026-11-18', ['a', 'b']],
    ['2026-11-19', ['c']],
    ['2026-11-20', ['d']],
  ])
  assert.deepEqual(groupByDate([]), [])
})

test('club ids match whether they are numbers or strings', () => {
  assert.equal(sameClub(7, '7'), true)
  assert.equal(sameClub('7', 7), true)
  assert.equal(sameClub(7, 8), false)
  assert.equal(sameClub(7, ''), false)
})

test('more from this club leaves out the open event and other clubs, and stops at three', () => {
  const open = event({ event_id: 'open', club_id: 1 })
  const events = [
    open,
    event({ event_id: 'o1', club_id: 2 }),
    event({ event_id: 'a', club_id: 1 }),
    event({ event_id: 'b', club_id: '1' }),
    event({ event_id: 'c', club_id: 1 }),
    event({ event_id: 'd', club_id: 1 }),
  ]
  assert.deepEqual(moreFromClub(events, open).map((item) => item.event_id), ['a', 'b', 'c'])
  assert.deepEqual(moreFromClub(events, open, 1).map((item) => item.event_id), ['a'])
  assert.deepEqual(moreFromClub([open], open), [])
})
