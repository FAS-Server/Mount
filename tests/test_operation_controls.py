import json
import re
from pathlib import Path
import pytest
from ruamel.yaml import YAML

def translate_real(monkeypatch, language):
    import mount.MountManager as mm
    import mount.cmd_tree as tree
    data = YAML().load((Path(__file__).resolve().parents[1]/'lang'/(language+'.yml')).read_text(encoding='utf-8'))['mount']
    def translate(key, **values):
        section, name = key.split('.')
        return data[section][name].format(**values)
    monkeypatch.setattr(mm, 'rtr', translate)
    monkeypatch.setattr(tree, 'rtr', translate)
    return data['flow']

@pytest.mark.parametrize('language', ['en_us','zh_cn'])
@pytest.mark.parametrize('reason', ['occupied','unchecked','missing','invalid'])
def test_real_language_list_reasons_and_no_action(environment, monkeypatch, language, reason):
    from mount.constants import MOUNTABLE_CONFIG
    m, _, Source = environment
    flow = translate_real(monkeypatch,language)
    target = Path(m.servers_as_list[1])
    config = target/MOUNTABLE_CONFIG
    if reason=='missing': m._config.available_servers[1]=str(target/'absent')
    elif reason=='invalid': config.write_text('{',encoding='utf-8')
    else:
        data=json.loads(config.read_text())
        data['occupied_by' if reason=='occupied' else 'checked']='other' if reason=='occupied' else False
        config.write_text(json.dumps(data))
    src=Source()
    m.list_servers(src)
    row=next(row for row in src.replies if flow[reason] in str(row))
    assert 'clickEvent' not in json.dumps(row.to_json_object())
    assert str(target.parent) not in str(row)
    print('LIST_REASON',language,reason,str(row))


def test_language_fields_match_and_utf8_is_valid():
    root = Path(__file__).resolve().parents[1]
    data = [YAML().load((root/'lang'/name).read_text(encoding='utf-8'))['mount']['flow'] for name in ['en_us.yml','zh_cn.yml']]
    assert data[0].keys() == data[1].keys()
    for key in data[0]:
        assert set(re.findall(r'{(\w+)}',data[0][key])) == set(re.findall(r'{(\w+)}',data[1][key]))
        assert '\ufffd' not in data[1][key]
