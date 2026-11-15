import { test } from 'node:test';
import assert from 'node:assert/strict';
import { geographicSplit, geographicAllocation } from '../src/geography.js';
import { loadExposureCategories } from '../lib/exposure-categories.mjs';
import { WORLD_COUNTRIES } from '../src/world-map.js';

test('geographic parser uses numeric CSV allocations only, with explicit non-country and missing buckets',()=>{
  assert.deepEqual(geographicSplit('Canada : 70 %; France : 30 %'),[{name:'Canada',kind:'place',percent:70},{name:'France',kind:'place',percent:30}]);
  assert.equal(geographicSplit('Aucun pays : 100 %')[0].kind,'no_country');
  assert.equal(geographicSplit('Sans objet pour une allocation; série de taux')[0].kind,'not_applicable');
  for(const invalid of ['Monde','Canada : 110 %','Canada : 60 %','Canada : -10 %; France : 110 %','Données non disponibles','']) assert.equal(geographicSplit(invalid)[0].kind,'unknown');
  assert.equal(geographicSplit('France : 99,5 %; Canada : 0,5 %')[0].percent,99.5);
});

test('real CSV geography keeps issuer domicile distinct from broad target-zone descriptions',async()=>{
  const {geographies}=await loadExposureCategories();
  assert.equal(Object.keys(geographies).length,82);
  assert.equal(geographies.NVDA.zone,'Monde');
  assert.deepEqual(geographies.NVDA.exposures,[{name:'États-Unis',kind:'place',percent:100}]);
  assert.equal(geographies.GLD.exposures[0].kind,'no_country');
  assert.match(geographies.NVDA.basis,/siège social/);
  const positions=[['SPY',20],['XIU.TO',20],['NVDA',10],['XBB.TO',25],['ZST.TO',15],['GLD',10]].map(([symbol,weight])=>({symbol,weight,name:symbol}));
  const result=geographicAllocation({positions},geographies);
  assert.deepEqual(result.map(x=>[x.name,x.weight]),[['Canada',60],['États-Unis',30],['Sans pays unique',10]]);
  assert.equal(result[0].contributors.length,3);
  assert.deepEqual(positions.map(x=>x.weight),[20,20,10,25,15,10]);
});

test('mixed exposures multiply position weights and preserve unknown holdings in the total',()=>{
  const records={MIX:{exposures:geographicSplit('Canada : 25 %; France : 75 %'),basis:'Fixture seulement'},WORLD:{exposures:geographicSplit('Aucun pays : 100 %')}};
  const result=geographicAllocation({positions:[{symbol:'MIX',name:'Mix',weight:40},{symbol:'WORLD',name:'World',weight:30},{symbol:'ABSENT',name:'Unknown',weight:30}]},records);
  assert.equal(result.reduce((s,x)=>s+x.weight,0),100);
  assert.equal(result.find(x=>x.name==='France').weight,30);
  assert.equal(result.find(x=>x.name==='Canada').weight,10);
  assert.equal(result.find(x=>x.kind==='unknown').weight,30);
  assert.equal(result.find(x=>x.kind==='no_country').weight,30);
  assert.equal(geographicAllocation({positions:[{symbol:'BAD',name:'Bad',weight:100}]},{BAD:{exposures:[{name:'Canada',kind:'place',percent:200}]}})[0].kind,'unknown');
});

test('world map uses generated real country geometry and contains the known portfolio countries',()=>{
  assert.equal(WORLD_COUNTRIES.length,176);
  assert.equal(new Set(WORLD_COUNTRIES.map(c=>c.id)).size,176);
  for(const id of ['CAN','USA','FRA','CHN']) {
    const country=WORLD_COUNTRIES.find(c=>c.id===id);
    assert.ok(country); assert.match(country.d,/^M/);
    assert.ok(country.x>=0&&country.x<=800&&country.y>=0&&country.y<=400);
  }
});
