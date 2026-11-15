"""Project the downloaded Natural Earth 110m countries into a local SVG module."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / 'assets/world-countries.geojson'
data = json.loads(source.read_text(encoding='utf-8'))
countries = []
for feature in data['features']:
    props = feature['properties']
    if props['ADM0_A3'] == 'ATA':
        continue
    geometry = feature['geometry']
    polygons = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
    paths = []
    for polygon in polygons:
        for ring in polygon:
            xy = [((lon + 180) * 800 / 360, (90 - lat) * 400 / 180) for lon, lat in ring]
            paths.append('M' + 'L'.join(f'{x:.2f},{y:.2f}' for x, y in xy) + 'Z')
    countries.append(dict(id=props['ADM0_A3'], name=props['NAME_FR'] or props['NAME'],
                          x=round((props['LABEL_X'] + 180)*800/360, 2),
                          y=round((90-props['LABEL_Y'])*400/180, 2), d=''.join(paths)))
header = '// Natural Earth 110m, public domain. Equirectangular projection; Antarctica omitted.\n'
header += '// Source SHA-256: ' + hashlib.sha256(source.read_bytes()).hexdigest() + '\n'
(root / 'src/world-map.js').write_text(header + 'export const WORLD_COUNTRIES = ' + json.dumps(countries, ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8')
print(f'Generated {len(countries)} country outlines.')
