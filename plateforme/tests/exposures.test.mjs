import assert from 'node:assert/strict';
import { test } from 'node:test';
import { validateExposureReview } from '../src/integration.js';

function exemple() {
  const dimension = () => ({ groups: [{ basis: 'GICS', weights_pct: { Technologie: 50 }, tickers: ['TEST'] }], covered_pct: 50, unclassified_pct: 50, missing_tickers: ['INCONNU'] });
  return { method: 'weighted_catalog_exposures_v1', dimensions: { sectors: dimension(), geography: dimension(), asset_classes: dimension() },
    preferred_sector_weight_pct: 50, preferred_sectors: ['Technologie'], insights: [], limitations: ['Données fictives pour le test.'],
    potential_assets: [{ ticker: 'AUTRE', sector: 'Technologie', current_measured_sector_pct: 50, description_fr: 'Description fictive.', status: 'to_study', applied: false }] };
}

test('les expositions partielles et les pistes non appliquées sont acceptées', () => {
  assert.equal(validateExposureReview(exemple()), true);
});

test('une couverture incohérente ou une piste déjà appliquée est refusée', () => {
  const inconsistent = exemple(); inconsistent.dimensions.sectors.covered_pct = 100;
  assert.equal(validateExposureReview(inconsistent), false);
  const totals = exemple(); totals.dimensions.geography.groups[0].weights_pct.Technologie = 60;
  assert.equal(validateExposureReview(totals), false);
  const applied = exemple(); applied.potential_assets[0].applied = true;
  assert.equal(validateExposureReview(applied), false);
});
