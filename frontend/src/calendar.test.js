import assert from 'node:assert/strict'
import test from 'node:test'

import { buildIcs, calendarWindow, googleCalendarUrl } from './calendar.js'

const event = {
  event_id: 'post:abc123',
  club_name: 'Hunter Coding Club',
  event_name: 'Intro to Git, Part 1',
  date: '2026-11-12',
  start_time: '17:00',
  end_time: '18:30',
  location: 'Hunter North 1001',
  free_food: true,
  post_link: 'https://instagram.com/p/abc123/',
  event_link: null,
}

test('uses the start and end time from the event', () => {
  assert.deepEqual(calendarWindow(event), {
    allDay: false,
    start: '20261112T170000',
    end: '20261112T183000',
  })
})

test('gives events with no end time a one hour slot', () => {
  const { end } = calendarWindow({ ...event, end_time: null })
  assert.equal(end, '20261112T180000')
})

test('ignores an end time that is before the start', () => {
  const { end } = calendarWindow({ ...event, end_time: '01:00' })
  assert.equal(end, '20261112T180000')
})

test('treats a date-only event as all day', () => {
  const dateOnly = { ...event, start_time: '00:00', end_time: null }
  assert.deepEqual(calendarWindow(dateOnly), {
    allDay: true,
    start: '20261112',
    end: '20261113',
  })
})

test('all day events roll over the end of the month', () => {
  const { end } = calendarWindow({ ...event, date: '2026-11-30', start_time: '00:00', end_time: null })
  assert.equal(end, '20261201')
})

test('google calendar link has the title, times and location', () => {
  const url = new URL(googleCalendarUrl(event))
  assert.equal(url.searchParams.get('text'), 'Intro to Git, Part 1')
  assert.equal(url.searchParams.get('dates'), '20261112T170000/20261112T183000')
  assert.equal(url.searchParams.get('location'), 'Hunter North 1001')
  assert.equal(url.searchParams.get('ctz'), 'America/New_York')
})

test('ics file escapes commas and uses windows line endings', () => {
  const ics = buildIcs(event, new Date('2026-11-09T12:00:00Z'))
  assert.ok(ics.startsWith('BEGIN:VCALENDAR\r\n'))
  assert.ok(ics.endsWith('END:VCALENDAR\r\n'))
  assert.ok(ics.includes('SUMMARY:Intro to Git\\, Part 1\r\n'))
  assert.ok(ics.includes('DTSTART:20261112T170000\r\n'))
  assert.ok(ics.includes('DTSTAMP:20261109T120000Z\r\n'))
})

test('ics file leaves out the location line when there is none', () => {
  const ics = buildIcs({ ...event, location: null })
  assert.ok(!ics.includes('LOCATION'))
})

test('ics file folds long lines', () => {
  const longName = { ...event, event_name: 'A'.repeat(200) }
  const lines = buildIcs(longName).split('\r\n')
  assert.ok(lines.every((line) => line.length <= 75))
})
