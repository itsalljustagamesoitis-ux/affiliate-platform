import { test } from 'node:test'
import assert from 'node:assert/strict'
import { classifyKeyword } from '../lib/classify-keyword.mjs'

test('comparison: vs / versus / compared', () => {
  assert.equal(classifyKeyword('Sony A7 IV vs Nikon Z6 III'), 'comparison')
  assert.equal(classifyKeyword('mirrorless vs DSLR cameras'), 'comparison')
  assert.equal(classifyKeyword('Sony A7 IV versus Canon EOS R5'), 'comparison')
  assert.equal(classifyKeyword('Sony A7C II compared to Fujifilm X-T5'), 'comparison')
  assert.equal(classifyKeyword('mirrorless vs. DSLR'), 'comparison')
})

test('review: review / hands-on / tested', () => {
  assert.equal(classifyKeyword('Sony A7 IV review'), 'review')
  assert.equal(classifyKeyword('Nikon Z8 hands-on'), 'review')
  assert.equal(classifyKeyword('Canon EOS R5 hands on'), 'review')
  assert.equal(classifyKeyword('Fujifilm X-T5 tested'), 'review')
})

test('roundup: best X for Y / best X under $N / top N', () => {
  assert.equal(classifyKeyword('best mirrorless cameras for beginners'), 'roundup')
  assert.equal(classifyKeyword('best tripods for travel photography'), 'roundup')
  assert.equal(classifyKeyword('best cameras under $1000'), 'roundup')
  assert.equal(classifyKeyword('top 5 camera lenses for portraits'), 'roundup')
  assert.equal(classifyKeyword('top 10 mirrorless cameras 2024'), 'roundup')
})

test('buyer_guide: bare best / buying guide / guide / how to choose', () => {
  assert.equal(classifyKeyword('best mirrorless cameras'), 'buyer_guide')
  assert.equal(classifyKeyword('best camera lenses'), 'buyer_guide')
  assert.equal(classifyKeyword('camera lens buying guide'), 'buyer_guide')
  assert.equal(classifyKeyword('mirrorless camera guide'), 'buyer_guide')
  assert.equal(classifyKeyword('how to choose a camera lens'), 'buyer_guide')
  assert.equal(classifyKeyword('how to pick the right tripod'), 'buyer_guide')
  assert.equal(classifyKeyword('how to select a camera bag'), 'buyer_guide')
})

test('empty / null / undefined defaults to buyer_guide', () => {
  assert.equal(classifyKeyword(''), 'buyer_guide')
  assert.equal(classifyKeyword(null), 'buyer_guide')
  assert.equal(classifyKeyword(undefined), 'buyer_guide')
})

test('comparison beats review signals', () => {
  assert.equal(classifyKeyword('Sony A7 IV vs Canon R5 in-depth review comparison'), 'comparison')
})

test('case-insensitive', () => {
  assert.equal(classifyKeyword('Sony A7 IV VS Nikon Z6'), 'comparison')
  assert.equal(classifyKeyword('Best Mirrorless Cameras'), 'buyer_guide')
  assert.equal(classifyKeyword('Sony A7 IV Review'), 'review')
})
