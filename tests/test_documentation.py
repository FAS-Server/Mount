"""Current README examples must describe supported operation configuration."""
import json,re
from pathlib import Path
import pytest
from mount.config import MountConfig

@pytest.mark.parametrize('name',['README.md','README_en.md'])
def test_documented_instance_configuration_has_no_unsupported_fields(name):
    document=(Path(__file__).resolve().parents[1]/name).read_text(encoding='utf-8')
    block=re.search(r'```json5\s*\n(.*?)\n```',document,re.S)[1]
    config=json.loads('\n'.join(line for line in block.splitlines() if not line.lstrip().startswith('//')))
    unsupported=set(config)-set(MountConfig().serialize())
    assert not unsupported, name+' documents unsupported fields: '+str(sorted(unsupported))
