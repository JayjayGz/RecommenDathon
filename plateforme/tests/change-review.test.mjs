import assert from 'node:assert/strict';
import { test } from 'node:test';
import { normalizeRecommendation, validateRecommendation, canRetainProposal } from '../src/integration.js';
import { simulationFixture } from './fixtures/change-review.mjs';

test('une analyse compatible reste séparée du portefeuille courant et survit à la normalisation', () => {
  const { initial, proposal } = simulationFixture();
  const current = normalizeRecommendation(initial).portfolio;
  const normalized = normalizeRecommendation(proposal);
  assert.deepEqual(normalized.changeReview, proposal.changeReview);
  assert.equal(canRetainProposal(normalized, current), true);
  assert.equal(current.positions[0].weight, 20);
  normalized.changeReview.applied = true;
  assert.equal(proposal.changeReview.applied, false);
  assert.equal(validateRecommendation(normalized), false);
});

test('une clarification, un avis absent ou un portefeuille devenu différent empêche la confirmation', () => {
  const { initial, proposal } = simulationFixture();
  const current = normalizeRecommendation(initial).portfolio;
  for (const verdict of ['clarification_required', 'not_retained']) {
    const candidate = structuredClone(proposal);
    candidate.changeReview.verdict = verdict;
    assert.equal(validateRecommendation(candidate), true);
    assert.equal(canRetainProposal(candidate, current), false);
  }
  const legacy = structuredClone(proposal); delete legacy.changeReview;
  assert.equal(canRetainProposal(legacy, current), false);
  assert.equal(canRetainProposal(proposal, { ...current, isDemo: true }), false);
  assert.equal(canRetainProposal(proposal, normalizeRecommendation(proposal).portfolio), false);
  const inconsistent = structuredClone(proposal);
  inconsistent.changeReview.assets[0].after_pct = 30;
  assert.equal(validateRecommendation(inconsistent), false);
});
