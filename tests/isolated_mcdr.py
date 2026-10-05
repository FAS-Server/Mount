"""Foreground real-MCDR smoke test with a disposable vanilla-output process.

Run with the same Python that has MCDR installed. No Java/world downloads,
network listener, production paths, or background service are used.
"""
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path


FAKE_SERVER = '''import sys, time, json
def plain(value):
    if isinstance(value, list):
        return ''.join(plain(v) for v in value)
    if isinstance(value, dict):
        return value.get('text','')+plain(value.get('extra',[]))
    return str(value)
def emit(text):
    print('[12:00:00] [Server thread/INFO]: '+text, flush=True)
emit('Starting minecraft server version 1.20.1')
emit('Done (0.01s)! For help, type "help"')
for line in sys.stdin:
    line = line.strip().lstrip('/')
    if line.startswith('execute at @p run '):
        line = line[len('execute at @p run '):]
    if line == 'stop':
        emit('Stopping server')
        time.sleep(.25)
        break
    elif line == 'list':
        emit('There are 3 of a max of 20 players online: Alice, Bob, Admin')
    elif line.startswith('testchat '):
        _, name, command = line.split(' ',2)
        emit('<'+name+'> '+command)
    elif line.startswith('tellraw '):
        emit('TEST_REPLY '+line+' PLAIN '+plain(json.loads(line.split(' ',2)[2])).replace(chr(10),' | '))
'''


def main():
    repository = Path(__file__).resolve().parents[1]
    language = sys.argv[1] if len(sys.argv) > 1 else 'en_us'
    sys.path.insert(0, str(repository))
    with tempfile.TemporaryDirectory(prefix='mount-isolated-') as temporary:
        root = Path(temporary)
        subprocess.run([sys.executable,'-m','mcdreforged','init'],cwd=root,check=True,
                       stdout=subprocess.DEVNULL)
        from ruamel.yaml import YAML
        yaml = YAML()
        config_path = root/'config.yml'
        config = yaml.load(config_path)
        current, target = root/'current', root/'target with spaces'
        start_command = '"{}" fake_server.py'.format(sys.executable)
        for slot in (current,target):
            (slot/'world'/'playerdata').mkdir(parents=True)
            (slot/'world'/'level.dat').write_bytes(b'disposable-current')
            (slot/'world'/'playerdata'/'Alice.dat').write_bytes(b'player')
            (slot/'template'/'world').mkdir(parents=True)
            (slot/'template'/'world'/'level.dat').write_bytes(b'disposable-template')
            (slot/'fake_server.py').write_text(FAKE_SERVER,encoding='utf-8')
            (slot/'mount.json').write_text(json.dumps({'checked':True,'start_command':start_command,
                'handler':'vanilla_handler','reset_path':'template','reset_type':'region'}))
        from mount.constants import MOUNTABLE_CONFIG, CONFIG_NAME
        if MOUNTABLE_CONFIG != 'mount.json':
            for slot in (current,target):
                (slot/'mount.json').rename(slot/MOUNTABLE_CONFIG)
        config.update({'working_directory':str(current),'start_command':start_command,
                       'handler':'vanilla_handler','language':language,'check_update':False,
                       'advanced_console':False, 'encoding':'utf-8', 'decoding':'utf-8'})
        yaml.dump(config,config_path)
        (root/CONFIG_NAME).parent.mkdir(parents=True, exist_ok=True)
        (root/CONFIG_NAME).write_text(json.dumps({'current_server':str(current),
            'available_servers':[str(current),str(target)],'servers_path':[str(root/'unused')],
            'overwrite_path':'','mount_name':'isolated','vote_cooldown':0,
            'force_players':['Admin'],'force_console':False,
            'backup_root':str(root/'backups'),'start_timeout':10,'stop_timeout':10}),encoding='utf-8')
        with zipfile.ZipFile(root/'plugins'/'Mount.pyz','w') as archive:
            for folder in ('mount','lang'):
                for path in (repository/folder).rglob('*'):
                    if path.is_file() and '__pycache__' not in path.parts:
                        archive.write(path,path.relative_to(repository))
            archive.write(repository/'mcdreforged.plugin.json','mcdreforged.plugin.json')
        process = subprocess.Popen([sys.executable,'-m','mcdreforged','start'],cwd=root,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
            env=dict(os.environ, PYTHONIOENCODING='utf-8'),
            text=True,encoding='utf-8',errors='replace')
        lines, output = queue.Queue(), []
        def read():
            for line in process.stdout:
                output.append(line)
                lines.put(re.sub(r'\x1b\[[0-9;]*m', '', line))
                # Closing a pipe before modern MCDR stops its console creates
                # an EOF input flood. Release the reader only after console stop.
                if '[MainThread/INFO]: bye' in line and not process.stdin.closed:
                    process.stdin.close()
        reader = threading.Thread(target=read)
        reader.start()
        def send(command):
            process.stdin.write(command+'\n')
            process.stdin.flush()
        def wait(pattern,timeout=20):
            deadline = time.monotonic()+timeout
            while time.monotonic()<deadline:
                try:
                    line = lines.get(timeout=.2)
                except queue.Empty:
                    if process.poll() is not None:
                        break
                    continue
                match = re.search(pattern,line)
                if match:
                    return match
            raise AssertionError('Missing '+pattern+'\n'+''.join(output[-40:]))
        try:
            wait(r'3 of a max of 20 players online')
            send('testchat Alice !!mount list')
            wait(r'PLAIN .*'+('Available' if language == 'en_us' else '可用'))
            navigation = wait(r'TEST_REPLY tellraw Alice .*1/1').string
            assert 'clickEvent' not in navigation
            send('testchat Alice !!mount switch '+str(target))
            creation = wait(r'Alice started switch vote.*Request ([a-f0-9]{32})' if language == 'en_us'
                            else r'Alice 发起切换投票.*请求 ([a-f0-9]{32})')
            vote_id = creation[1]
            assert '60.0%' in creation.string and '2/3' in creation.string
            send('testchat Alice !!mount vote '+vote_id+' yes')
            send('testchat Bob !!mount vote '+vote_id+' yes')
            wait(r'switch request '+vote_id+r'.*Startup verified' if language == 'en_us'
                 else r'切换 请求 '+vote_id+r'.*已验证启动完成')
            assert json.loads((root/CONFIG_NAME).read_text())['current_server']==str(target)
            send('testchat Alice !!mount reset')
            reset_id = wait(r'Alice started reset vote.*Request ([a-f0-9]{32})' if language == 'en_us'
                            else r'Alice 发起重置投票.*请求 ([a-f0-9]{32})')[1]
            send('testchat Bob !!mount status '+reset_id)
            wait(r'TEST_REPLY tellraw Bob .*PLAIN .*'+('Reset mode region' if language == 'en_us' else '重置模式 region'))
            send('testchat Alice !!mount cancel '+reset_id)
            wait(r'Vote '+reset_id+r' cancelled' if language == 'en_us' else r'投票 '+reset_id+r' 已取消')
            send('!!mount backup')
            wait(r'Server is stopping briefly' if language == 'en_us' else r'服务器将短暂停止')
            send('!!MCDR plugin reload mount')
            backup_id = wait(r'backup request .*verified backup ([a-f0-9]{32}).*Startup verified' if language == 'en_us'
                             else r'备份 请求 .*已校验备份 ([a-f0-9]{32}).*已验证启动完成')[1]
            assert (root/'backups'/backup_id/'manifest.json').is_file()
            send('testchat Admin !!mount force reset')
            force_id = wait(r'Force reset:.*Request ([a-f0-9]{32})' if language == 'en_us'
                            else r'强制重置：.*请求 ([a-f0-9]{32})')[1]
            send('testchat Admin !!mount force confirm '+force_id)
            wait(r'reset request '+force_id+r'.*Startup verified' if language == 'en_us'
                 else r'重置 请求 '+force_id+r'.*已验证启动完成')
            assert (target/'world'/'level.dat').read_bytes()==b'disposable-template'
            assert (target/'world'/'playerdata'/'Alice.dat').read_bytes()==b'player'
            slot_config = json.loads((target/MOUNTABLE_CONFIG).read_text())
            slot_config['reset_type'] = 'full'
            (target/MOUNTABLE_CONFIG).write_text(json.dumps(slot_config))
            send('testchat Admin !!mount force reset')
            force_id = wait(r'Force reset:.*Request ([a-f0-9]{32})' if language == 'en_us'
                            else r'强制重置：.*请求 ([a-f0-9]{32})')[1]
            send('testchat Admin !!mount force confirm '+force_id)
            wait(r'reset request '+force_id+r'.*Startup verified' if language == 'en_us'
                 else r'重置 请求 '+force_id+r'.*已验证启动完成')
            assert not (target/'world'/'playerdata').exists()
            send('!!MCDR plugin reload mount')
            wait(r'3 of a max of 20 players online')
            send('stop')
            wait(r'bye')
            process.wait(timeout=20)
            assert process.returncode==0, 'Exit '+str(process.returncode)+'\n'+''.join(output[-25:])
            assert not any('Error loading plugin' in line or 'Error when executing' in line for line in output)
            print('PASS '+language+': real MCDR load, list, snapshot, vote, reset scope for other voters, spaced-path switch, backup, full/region reset, reload during execution, shutdown')
        finally:
            if process.poll() is None:
                import psutil
                parent = psutil.Process(process.pid)
                for child in parent.children(recursive=True):
                    child.kill()
                process.kill()
                process.wait(timeout=10)
            reader.join(timeout=10)
            (repository/'isolated-mcdr.log').write_text(''.join(output),encoding='utf-8')
            rendered = [line.split(' PLAIN ', 1)[1].strip() for line in output if ' PLAIN ' in line
                        and ('started switch vote' in line or '发起切换投票' in line
                             or 'Reset mode' in line or '重置模式' in line
                             or '[Available]' in line or '[可用]' in line)]
            (repository/('rendered-'+language+'.txt')).write_text('\n'.join(dict.fromkeys(rendered)), encoding='utf-8')


if __name__ == '__main__':
    main()
