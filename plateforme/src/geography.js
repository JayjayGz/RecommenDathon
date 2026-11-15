// Only the explicitly quantified geographic split is used for portfolio weights.
export function geographicSplit(value) {
  const unknown = [{ name: 'Non renseigné', kind: 'unknown', percent: 100 }];
  if (typeof value !== 'string' || !value.trim()) return unknown;
  if (/^Sans objet pour une allocation/i.test(value.trim())) return [{ name: 'Non applicable', kind: 'not_applicable', percent: 100 }];
  const parts=value.split(';').map(text=>text.trim());
  const parsed=[];
  for(const part of parts) {
    const match=part.match(/^([^:]+)\s*:\s*(\d+(?:[.,]\d+)?)\s*%$/u);
    if(!match) return unknown;
    const percent=Number(match[2].replace(',','.'));
    if(!Number.isFinite(percent)||percent<0||percent>100) return unknown;
    const name=match[1].trim().normalize('NFC');
    const noCountry=/^Aucun pays$/i.test(name);
    if(percent>0) parsed.push({name:noCountry?'Sans pays unique':name,kind:noCountry?'no_country':'place',percent});
  }
  if(!parsed.length || Math.abs(parsed.reduce((sum,p)=>sum+p.percent,0)-100)>1e-6) return unknown;
  return parsed;
}

export function geographicAllocation(portfolio, records={}) {
  const groups=new Map();
  for(const position of portfolio.positions) {
    const record=Object.hasOwn(records,position.symbol.trim().toUpperCase())?records[position.symbol.trim().toUpperCase()]:null;
    const split=record?.exposures || geographicSplit('');
    // Server records are untrusted at the browser boundary: fail to unknown, never guess.
    const valid=Array.isArray(split)&&split.length>0&&split.every(p=>p&&typeof p.name==='string'&&p.name.trim()&&['place','no_country','unknown','not_applicable'].includes(p.kind)&&Number.isFinite(p.percent)&&p.percent>0&&p.percent<=100)
      && Math.abs(split.reduce((sum,p)=>sum+p.percent,0)-100)<1e-6;
    for(const part of valid?split:geographicSplit('')) {
      const key=part.kind+':'+part.name;
      const group=groups.get(key)||{name:part.name,kind:part.kind,weight:0,contributors:[]};
      const contribution=position.weight*part.percent/100;
      group.weight+=contribution;
      group.contributors.push({symbol:position.symbol,name:position.name,weight:contribution,sourcePercent:part.percent,
        basis:typeof record?.basis==='string'?record.basis:'',zone:typeof record?.zone==='string'?record.zone:'',date:typeof record?.date==='string'?record.date:'',limitations:typeof record?.limitations==='string'?record.limitations:''});
      groups.set(key,group);
    }
  }
  return [...groups.values()].sort((a,b)=>b.weight-a.weight);
}
