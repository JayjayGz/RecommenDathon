import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadExposureCategories, parseExposureCategories } from '../lib/exposure-categories.mjs';
import { allocationGroups, exposureCategory } from '../src/integration.js';

test('category source matches the supplied CSV, not model group names',async()=>{
  const {categories}=await loadExposureCategories();
  assert.equal(Object.keys(categories).length,82);
  assert.equal(categories.NVDA,'equity');
  assert.equal(categories.SPY,'etf_equity');
  assert.equal(categories['XBB.TO'],'etf_bond');
  assert.equal(categories.GLD,'etf_commodity');
  const positions=[{symbol:'NVDA',weight:20,group:'WRONG'},{symbol:'SPY',weight:30,group:'WRONG'},{symbol:'XBB.TO',weight:40,group:'WRONG'},{symbol:'MISSING',weight:10,group:'Actions'}];
  const snapshot=structuredClone(positions);
  assert.deepEqual(allocationGroups({positions},categories).map(({name,weight})=>[name,weight]),[['Actions',20],['FNB d’actions',30],['FNB obligataires',40],['Non classé',10]]);
  assert.deepEqual(positions,snapshot);
  assert.equal(exposureCategory(' nvda ',categories).code,'equity');
  assert.equal(exposureCategory('UNKNOWN',categories).code,'unclassified');
});

test('CSV reader handles quoted commas, escaped quotes, multiline descriptions and BOM',()=>{
  const csv='\uFEFFticker,description,asset_class\r\nSPY,"First, line\nsecond ""quote""",etf_equity\r\nNVDA,Nvidia,equity';
  assert.deepEqual({...parseExposureCategories(csv)},{SPY:'etf_equity',NVDA:'equity'});
  for(const invalid of ['ticker,asset_class\nSPY,etf_equity\nSPY,equity','ticker,asset_class\nSPY,','ticker,asset_class\nSPY,"unfinished','wrong,headers\na,b']) assert.throws(()=>parseExposureCategories(invalid));
});
