import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { geographicSplit } from '../src/geography.js';

export function parseExposureCategories(csv, withGeography = false) {
  const rows = []; let row = [], field = '', quoted = false;
  const input = csv.replace(/^\uFEFF/, '');
  for (let i=0; i<input.length; i++) {
    const c=input[i];
    if (c==='"') {
      if (quoted && input[i+1]==='"') { field+='"'; i++; }
      else if (quoted || !field) quoted=!quoted;
      else throw new Error('CSV invalide.');
    } else if (!quoted && (c===',' || c==='\n' || c==='\r')) {
      row.push(field);field='';
      if (c!==',') { if(row.some(x=>x.trim())) rows.push(row); row=[]; if(c==='\r' && input[i+1]==='\n') i++; }
    } else field+=c;
  }
  if(quoted) throw new Error('CSV tronqué.');
  if(field || row.length) { row.push(field); if(row.some(x=>x.trim())) rows.push(row); }
  const headers=rows.shift() || [];
  const ticker=headers.indexOf('ticker'), type=headers.indexOf('asset_class');
  if(ticker<0 || type<0) throw new Error('Colonnes ticker/asset_class manquantes.');
  const categories=Object.create(null);
  const geographies=Object.create(null);
  for(const values of rows) {
    if(values.length!==headers.length) throw new Error('Ligne CSV invalide.');
    const symbol=values[ticker].trim().toUpperCase(), assetClass=values[type].trim();
    if(!symbol || !assetClass || Object.hasOwn(categories,symbol)) throw new Error('Classification absente ou symbole dupliqué.');
    categories[symbol]=assetClass;
    const value=key=>values[headers.indexOf(key)] || '';
    geographies[symbol]={exposures:geographicSplit(value('repartition_geographique')),zone:value('pays_ou_zone_visee'),basis:value('base_repartition_geographique'),date:value('date_repartition_geographique'),limitations:value('limites_repartitions')};
  }
  if(!Object.keys(categories).length) throw new Error('Classification vide.');
  return withGeography ? {categories,geographies} : categories;
}

export async function loadExposureCategories() {
  const bytes=await readFile(new URL('../../dataset/exposures_profile_tickers.csv',import.meta.url));
  return { ...parseExposureCategories(bytes.toString('utf8'),true), source:'exposures_profile_tickers.csv', sha256:createHash('sha256').update(bytes).digest('hex') };
}
