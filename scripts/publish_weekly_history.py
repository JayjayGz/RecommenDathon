"""Publish the verified supplement with an original backup and atomic replace."""
import hashlib
import json
import os
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root / 'livrables/historique_hebdomadaire'
manifest_path = folder / 'top100_hebdo_2016_manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
target_dir = Path(r'C:/Users/alibe/Downloads/Datathon2026/Datathon2026/alphaforge_starter').resolve()
target = target_dir / 'top100_hebdo_2016 (2).csv'
output = folder / 'top100_hebdo_2016_complet.csv'
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert target.resolve().parent == target_dir
original_hash = manifest['input_files']['weekly']['sha256']
updated_hash = manifest['outputs']['weekly']['sha256']
assert digest(output) == updated_hash, 'Output changed after verification'
assert digest(target) == original_hash, 'Original changed after verification; refusing overwrite'
backup = target_dir / f'top100_hebdo_2016 (2).avant_ajouts_{original_hash[:8]}.csv'
if backup.exists():
    assert digest(backup) == original_hash, 'Backup name collision'
else:
    shutil.copyfile(target, backup)
assert digest(backup) == original_hash
staging = target_dir / f'top100_hebdo_2016.updated_{updated_hash[:8]}.tmp'
assert staging.resolve().parent == target_dir
assert not staging.exists(), 'Staging file already exists'
shutil.copyfile(output, staging)
assert digest(staging) == updated_hash
os.replace(staging, target)
assert digest(target) == updated_hash
downloads = Path(r'C:/Users/alibe/Downloads').resolve()
delivery = downloads / output.name
if delivery.exists() and digest(delivery) != updated_hash:
    delivery = downloads / f'{output.stem}_{updated_hash[:8]}.csv'
assert not delivery.exists() or digest(delivery) == updated_hash, 'Delivery name collision'
shutil.copyfile(output, delivery)
manifest['input_files']['weekly']['preserved_backup'] = str(backup)
manifest['publication'] = {'updated_original': str(target), 'delivery_copy': str(delivery),
                           'original_sha256': original_hash, 'updated_sha256': updated_hash,
                           'backup_sha256': digest(backup), 'verified_copy_sha256': digest(delivery)}
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
for source in [manifest_path, folder / 'top100_hebdo_2016_couverture_ajouts.csv']:
    dest = downloads / source.name
    if dest.exists() and digest(dest) != digest(source):
        dest = downloads / f'{source.stem}_{updated_hash[:8]}{source.suffix}'
    assert not dest.exists() or digest(dest) == digest(source)
    shutil.copyfile(source, dest)
print(json.dumps(manifest['publication'],ensure_ascii=False,indent=2))
