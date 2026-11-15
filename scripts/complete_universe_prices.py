"""Append real Friday closes for universe members lacking price histories."""
import csv
import io
import json
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone
from urllib.parse import quote

import pandas as pd
from extend_weekly_history import sha256, COLUMNS, NUMERIC
from rebuild_weekly_friday import friday_last, yahoo_daily

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'livrables/historique_hebdomadaire'
OUT=BASE/'complement_univers'
OUT.mkdir(exist_ok=True)
target=Path('C:/Users/alibe/Downloads/price_weekly_compelt.csv')
universe=Path('C:/Users/alibe/Downloads/Datathon2026/Datathon2026/alphaforge_starter/assets_universe_complet.csv')
selection=Path('C:/Users/alibe/Downloads/asset_selection.csv')
u=pd.read_csv(universe);s=pd.read_csv(selection);old=pd.read_csv(target,parse_dates=['date'],float_precision='round_trip')
assert set(s.ticker)<=set(u.ticker)
excluded=u.loc[(u.asset_class=='bond_yield') | (u.ticker=='^VIX')]
eligible=set(u.ticker)-set(excluded.ticker)
missing=sorted(eligible-set(old.ticker))
assert missing==['CNQ.TO','MFC.TO','XBB.TO','XIU.TO'], missing
old_hash=sha256(target);original=target.read_bytes()
sources=[]
for ticker in missing:
    path=OUT/(ticker+'.json')
    url='https://query2.finance.yahoo.com/v8/finance/chart/'+quote(ticker,safe='')+'?period1=1451606400&period2=1794787200&interval=1d&events=history&includeAdjustedClose=true'
    if not path.exists():
        subprocess.run(['curl.exe','--silent','--show-error','--fail','--location','--max-time','35','-A','Mozilla/5.0',url,'-o',str(path)],check=True)
    payload=json.loads(path.read_bytes())
    assert not payload['chart']['error']
    assert payload['chart']['result'][0]['meta']['symbol']==ticker
    sources.append(dict(ticker=ticker,path=str(path),sha256=sha256(path),url=url,status='complete',retrieved_at_utc=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()))
daily,meta,discarded=yahoo_daily({'sources':sources})
added=friday_last(daily,'2016-01-01','2026-11-15')
assert set(added.ticker)==set(missing)
for row in added.to_dict('records'):
    response=json.loads(Path(row['source_path']).read_bytes())['chart']['result'][0]
    ix=int(row['source_index']);q=response['indicators']['quote'][0]
    for field in ['open','high','low','close','volume']: assert row[field]==q[field][ix]
    assert row['adj_close']==response['indicators']['adjclose'][0]['adjclose'][ix]
    assert row['currency']==response['meta']['currency']==u.loc[u.ticker==row['ticker'],'currency'].iloc[0]
backup=OUT/'price_weekly_avant_ajouts.csv'
if backup.exists(): assert backup.read_bytes()==original
else: backup.write_bytes(original)
text=added[COLUMNS].to_csv(index=False,header=False,date_format='%Y-%m-%d',lineterminator='\n')
new=original+(b'' if original.endswith(b'\n') else b'\n')+text.encode('utf-8')
local=OUT/'price_weekly_compelt.csv';local.write_bytes(new)
result=pd.read_csv(local,parse_dates=['date'],float_precision='round_trip')
assert local.read_bytes().startswith(original)
assert result.iloc[:len(old)].equals(old)
assert not result.duplicated(['ticker','date']).any()
assert eligible<=set(result.ticker)
assert (result.close>0).all() and result.close.notna().all()
assert '^VIX' not in set(result.ticker)
assert sha256(target)==old_hash
# Backups and technical files remain in the project, not Downloads.
stage=target.with_suffix('.updated.tmp');stage.write_bytes(new);stage.replace(target)
assert target.read_bytes()==new
for p in [BASE/'top100_hebdo_2016_complet.csv',BASE/'clotures_vendredi/top100_hebdo_2016_complet.csv']:
    assert sha256(p)==old_hash
    shutil.copyfile(local,p)
current=BASE/'clotures_vendredi'
for name,filtered in [('top100_hebdo_2016_sources_lignes.csv',False),('top100_hebdo_2016_couverture.csv',True),('top100_hebdo_2016_manifest.json',True),('verification.json',True)]:
    p=current/name
    if p.exists(): shutil.copy2(p,OUT/('previous_'+name))
audit=pd.read_csv(current/'top100_hebdo_2016_sources_lignes.csv',low_memory=False)
new_audit=added.copy();new_audit['provider']='Yahoo Finance';new_audit['price_policy']='last available regular-session close in the Friday-ending week';new_audit['bar_interval']='1d'
new_audit['target_timestamp']=new_audit.date.dt.tz_localize('America/Toronto').add(pd.Timedelta(hours=16)).map(lambda d:d.isoformat())
new_audit['date']=new_audit.date.dt.strftime('%Y-%m-%d')
audit=pd.concat([audit,new_audit.reindex(columns=audit.columns)],ignore_index=True)
audit.to_csv(current/'top100_hebdo_2016_sources_lignes.csv',index=False)
coverage=pd.read_csv(current/'top100_hebdo_2016_couverture.csv')
extra=[]
for ticker,g in added.groupby('ticker'):
    extra.append(dict(ticker=ticker,kind=meta[ticker]['kind'],currency=meta[ticker]['currency'],provider='Yahoo Finance',rows=len(g),verified_prices=len(g),missing_prices=0,first_price_week=g.date.min().date().isoformat(),last_price_week=g.date.max().date().isoformat(),weeks_without_price=len(pd.date_range('2016-01-01','2026-11-15',freq='W-FRI').difference(g.date)),price_method='regular_session_close',prior_session_rows=int((g.source_date!=g.date.dt.strftime('%Y-%m-%d')).sum()),crypto_missing_adjusted_close=False))
pd.concat([coverage,pd.DataFrame(extra)],ignore_index=True).to_csv(current/'top100_hebdo_2016_couverture.csv',index=False)
m=json.loads((current/'top100_hebdo_2016_manifest.json').read_text(encoding='utf-8'))
m['total_rows']=m['verified_close_rows']=len(result);m['tickers']=result.ticker.nunique()
m['coverage']+=extra
m['universe_completion']={'universe':str(universe),'universe_sha256':sha256(universe),'selection_sha256':sha256(selection),'added_tickers':missing,'added_rows':len(added),'sources':sources,'excluded_from_price_requirement':excluded[['ticker','asset_class']].to_dict('records'),'all_eligible_universe_assets_have_prices':True}
for entry in m['outputs'].values():entry['sha256']=sha256(Path(entry['path']))
m['publication']=[{'target':str(target),'sha256':sha256(target)}]
for p in [current/'top100_hebdo_2016_manifest.json',BASE/'top100_hebdo_2016_manifest.json']:
    p.write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
report=dict(status='complete',roles=['data','infrastructure','evidence'],next_owner='user',selection_in_universe=len(s),universe_rows=len(u),price_assets=int(result.ticker.nunique()),price_rows=len(result),added_tickers=missing,added_rows=len(added),unpriced_universe=excluded[['ticker','asset_class']].to_dict('records'),source_values_verified=True,existing_bytes_preserved=True,output_sha256=sha256(target))
(OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
