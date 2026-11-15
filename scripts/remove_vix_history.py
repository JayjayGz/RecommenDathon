"""Remove only VIX rows from current exports; preserve all other bytes."""
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'livrables/historique_hebdomadaire'
CURRENT = BASE / 'clotures_vendredi'
DOWNLOAD = Path('C:/Users/alibe/Downloads/top100_hebdo_2016_complet_sans_vix.csv')
EXPECTED = '6b6611f04dac87e78eef47598d718a8227dcf99fdf1fe7c4f3b2d99b72e97e88'
hash_bytes = lambda b: hashlib.sha256(b).hexdigest()
backup = BASE / 'avant_retrait_vix'
backup.mkdir(exist_ok=True)

def filtered(path):
    data = path.read_bytes()
    lines = data.splitlines(keepends=True)
    names = next(csv.reader([lines[0].decode('utf-8')]))
    index = names.index('ticker')
    retained, removed = [lines[0]], 0
    for line in lines[1:]:
        row = next(csv.reader([line.decode('utf-8')]))
        if row[index] in {'^VIX', 'VIX'}:
            removed += 1
        else:
            retained.append(line)
    return b''.join(retained), removed

targets = [DOWNLOAD, BASE/'top100_hebdo_2016_complet.csv', CURRENT/'top100_hebdo_2016_complet.csv']
for path in targets[1:]:
    assert hash_bytes(path.read_bytes()) == EXPECTED, f'Changed input: {path}'
new, removed = filtered(BASE/'top100_hebdo_2016_complet.csv')
assert removed == 567
rows = list(csv.DictReader(io.StringIO(new.decode('utf-8'))))
assert len(rows) == 68804 and len({r['ticker'] for r in rows}) == 123
assert not any(r['ticker'] in {'VIX','^VIX'} for r in rows)
assert hash_bytes((backup/'top100_hebdo_2016_complet.csv').read_bytes()) == EXPECTED
for name in ['top100_hebdo_2016_manifest.json','verification.json','top100_hebdo_2016_sources_lignes.csv','top100_hebdo_2016_couverture.csv']:
    shutil.copy2(CURRENT/name, backup/name)
for path in targets:
    temporary = path.with_suffix('.sans_vix.tmp')
    temporary.write_bytes(new)
    try:
        temporary.replace(path)
    except PermissionError:
        # Some Windows editors allow writes but hold a lock against renaming.
        # The verified original has already been preserved above.
        path.write_bytes(new)
        if path.read_bytes() == new:
            temporary.unlink()
    assert path.read_bytes() == new
for name in ['top100_hebdo_2016_sources_lignes.csv','top100_hebdo_2016_couverture.csv']:
    path = CURRENT/name
    content, count = filtered(path)
    assert count == (567 if 'sources_lignes' in name else 1)
    path.write_bytes(content)
manifest_path = CURRENT/'top100_hebdo_2016_manifest.json'
m = json.loads(manifest_path.read_text(encoding='utf-8'))
m['total_rows'] = m['verified_close_rows'] = len(rows)
m['tickers'] = 123
m['coverage'] = [r for r in m['coverage'] if r['ticker'] != '^VIX']
m['official_daily_close_tickers'].remove('^VIX')
m['user_exclusions'] = ['^VIX']
m['locked_original_download'] = 'C:/Users/alibe/Downloads/top100_hebdo_2016_complet.csv remains locked by another process; replacement pending'
m['exclusion_change'] = {'previous_sha256':EXPECTED,'removed_rows':removed,'backup':str(backup),
                         'check':'All non-VIX CSV lines preserved byte-for-byte',
                         'roles':['data','evidence'],'status':'complete','next_owner':'user'}
for entry in m['outputs'].values():
    entry['sha256'] = hash_bytes(Path(entry['path']).read_bytes())
m['previous_publication'] = m.pop('publication', [])
m['publication'] = [{'target':str(p),'sha256':hash_bytes(new)} for p in targets]
manifest_path.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
shutil.copyfile(manifest_path,BASE/manifest_path.name)
verification = {'status':'passed','rows':len(rows),'tickers':123,'removed_vix_rows':removed,
                'sha256':hash_bytes(new),'all_other_csv_lines_unchanged':True,
                'scope':'Filtering and exact byte preservation checks; prior source verification preserved in backup'}
(CURRENT/'verification.json').write_text(json.dumps(verification,indent=2)+'\n',encoding='utf-8')
readme = BASE/'README.md'
text = readme.read_text(encoding='utf-8')
text = text.replace('**124 actifs, dont les 34 sélectionnés ; 69 371 cours `close` renseignés**',
                    '**123 actifs, dont les 34 sélectionnés ; 68 804 cours `close` renseignés**')
text = text.replace(EXPECTED,hash_bytes(new))
text += '\nRetrait demandé du VIX : 567 lignes supprimées des exports courants ; toutes les autres lignes sont conservées octet pour octet. Les vérifications précédentes sont archivées dans `avant_retrait_vix/`. Aucun autre filtre ni recalcul des cours.\n'
readme.write_text(text,encoding='utf-8')
print(json.dumps(verification,indent=2))
