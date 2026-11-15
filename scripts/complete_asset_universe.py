"""Append missing selection metadata from the supplied universe_v2 literal."""
import ast
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = Path('C:/Users/alibe/Downloads/Datathon2026/Datathon2026/alphaforge_starter/assets_universe_complet.csv')
SELECTION = Path('C:/Users/alibe/Downloads/asset_selection.csv')
SOURCE = ROOT/'universe_v2.py'
OUT = ROOT/'livrables/univers_actifs'
OUT.mkdir(exist_ok=True)
sha = lambda b: hashlib.sha256(b).hexdigest()
original = TARGET.read_bytes()
rows = list(csv.DictReader(io.StringIO(original.decode('utf-8-sig'))))
selected = list(csv.DictReader(io.StringIO(SELECTION.read_text(encoding='utf-8-sig'))))
fields = list(rows[0])
symbols = {r['ticker'] for r in rows}
missing = {r['ticker'] for r in selected} - symbols
tree = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
metadata = {}
for node in tree.body:
    if isinstance(node, ast.Assign):
        try: value = ast.literal_eval(node.value)
        except (ValueError, TypeError): continue
        if isinstance(value,list):
            for item in value:
                if isinstance(item,tuple) and len(item)==6:
                    metadata[item[0]] = dict(zip(fields[1:],item))
assert missing and missing <= set(metadata), 'Missing supplied metadata'
assert len(symbols)==len(rows), 'Existing duplicates'
next_id = max(int(r['asset_id'][1:]) for r in rows)+1
additions = []
for index,ticker in enumerate(sorted(missing)):
    additions.append(dict(asset_id=f'A{next_id+index:02d}',**metadata[ticker]))
buffer = io.StringIO(newline='')
writer = csv.DictWriter(buffer,fieldnames=fields,lineterminator='\n')
writer.writerows(additions)
new = original + (b'' if original.endswith(b'\n') else b'\n') + buffer.getvalue().encode('utf-8')
check = list(csv.DictReader(io.StringIO(new.decode('utf-8-sig'))))
assert check[:len(rows)] == rows and new.startswith(original)
assert {r['ticker'] for r in selected} <= {r['ticker'] for r in check}
assert len({r['ticker'] for r in check})==len(check)
assert len({r['asset_id'] for r in check})==len(check)
backup = OUT/f'assets_universe_avant_{sha(original)[:8]}.csv'
if backup.exists(): assert backup.read_bytes()==original
else: backup.write_bytes(original)
local = OUT/'assets_universe_complet.csv'
local.write_bytes(new)
assert TARGET.read_bytes()==original, 'Concurrent input change'
stage = TARGET.with_suffix('.updated.tmp')
stage.write_bytes(new)
stage.replace(TARGET)
assert TARGET.read_bytes()==local.read_bytes()==new
report = dict(status='complete',roles=['data','screening'],next_owner='user',
              original_rows=len(rows),added=len(additions),total_rows=len(check),selection_covered=len(selected),
              added_tickers=sorted(missing),original_sha256=sha(original),output_sha256=sha(new),
              metadata_source=str(SOURCE),metadata_source_sha256=sha(SOURCE.read_bytes()),
              selection_sha256=sha(SELECTION.read_bytes()),target=str(TARGET),backup=str(backup),
              added_asset_classes=sorted({r['asset_class'] for r in additions}),
              checks=['34 selected symbols covered','original rows and bytes preserved','unique symbols and IDs','published bytes verified'],
              note='etf_balanced is copied from the supplied metadata, not inferred; downstream consumers must support it.')
(OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
