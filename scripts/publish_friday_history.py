"""Publish verified last-price CSVs after hash checks and immutable backups."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

from extend_weekly_history import sha256

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'livrables/historique_hebdomadaire/clotures_vendredi'
DOWNLOADS = Path('C:/Users/alibe/Downloads')
OLD_HASH = 'a977af976671386e14c8fca5ad63a20ea1290425918cc8622c90f53b92606034'


def publish() -> dict:
    manifest_path = FOLDER / 'top100_hebdo_2016_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    verification = json.loads((FOLDER / 'verification.json').read_text(encoding='utf-8'))
    if verification['status'] != 'passed' or verification['rows'] != manifest['total_rows']:
        raise ValueError('Current verification missing or incompatible')
    for record in manifest['outputs'].values():
        if sha256(Path(record['path'])) != record['sha256']:
            raise ValueError('Output changed since verification')
    source = Path(manifest['outputs']['weekly']['path'])
    new_hash = sha256(source)
    targets = [DOWNLOADS / 'top100_hebdo_2016_complet.csv',
               DOWNLOADS / 'Datathon2026/Datathon2026/alphaforge_starter/top100_hebdo_2016 (2).csv',
               ROOT / 'livrables/historique_hebdomadaire/top100_hebdo_2016_complet.csv']
    for target in targets:
        if sha256(target) != OLD_HASH:
            raise ValueError(f'Existing target changed; refusing overwrite: {target}')
    publications = []
    for target in targets:
        backup = target.with_name(target.stem + '.moyennes_' + OLD_HASH[:8] + target.suffix)
        if backup.exists():
            if sha256(backup) != OLD_HASH:
                raise ValueError('Conflicting backup')
        else:
            shutil.copy2(target, backup)
        if sha256(backup) != OLD_HASH:
            raise ValueError('Backup failed verification')
        stage = target.with_name(target.name + '.clotures.tmp')
        shutil.copyfile(source, stage)
        if sha256(stage) != new_hash:
            raise ValueError('Staged copy failed verification')
        publications.append(dict(target=str(target), backup=str(backup), stage=str(stage)))
    for record in publications:
        target, stage = Path(record['target']), Path(record['stage'])
        if sha256(target) != OLD_HASH:
            raise ValueError('Concurrent change detected before replacement')
        stage.replace(target)
        if sha256(target) != new_hash:
            raise ValueError('Published CSV failed verification')
        record.pop('stage')
        record['sha256'] = new_hash
    manifest['publication'] = publications
    manifest['previous']['preserved_backups'] = [r['backup'] for r in publications]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # Preserve earlier method manifests before installing the current manifest.
    for parent in [DOWNLOADS, ROOT / 'livrables/historique_hebdomadaire']:
        old_manifest = parent / manifest_path.name
        if old_manifest.exists():
            old_backup = parent / ('top100_hebdo_2016_manifest.moyennes_' + OLD_HASH[:8] + '.json')
            if not old_backup.exists():
                shutil.copy2(old_manifest, old_backup)
        shutil.copyfile(manifest_path, old_manifest)
    for name in ['top100_hebdo_2016_couverture.csv', 'top100_hebdo_2016_sources_lignes.csv']:
        shutil.copyfile(FOLDER / name, DOWNLOADS / name)
        if sha256(FOLDER / name) != sha256(DOWNLOADS / name):
            raise ValueError('Published audit/coverage failed verification')
    return dict(status='published', rows=manifest['total_rows'], tickers=manifest['tickers'],
                sha256=new_hash, publications=publications)


if __name__ == '__main__':
    print(json.dumps(publish(), indent=2))
