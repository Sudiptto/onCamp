import assert from 'node:assert/strict'
import test from 'node:test'

import { formatTimeRange } from './dates.js'

test('formats event times with an optional end', () => {
  assert.equal(formatTimeRange('17:00', '18:30'), '5:00 PM – 6:30 PM')
  assert.equal(formatTimeRange('17:00', null), '5:00 PM')
  assert.equal(formatTimeRange(null, null), 'Time not specified')
})
