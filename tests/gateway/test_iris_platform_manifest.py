import yaml
from pathlib import Path

def test_iris_plugin_manifest_exists_and_valid():
    p = Path('plugins/platforms/iris/plugin.yaml')
    assert p.exists(), f'Manifest not found at {p}'
    data = yaml.safe_load(p.read_text())
    assert data['name'] == 'iris-platform'
    assert data['kind'] == 'platform'
    assert 'iris' in data.get('description', '').lower()
