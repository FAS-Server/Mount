"""Foreground real-MCDR smoke test with a disposable vanilla-output process.

Run with the same Python that has MCDR installed. No Java/world downloads,
network listener, production paths, or background service are used.
"""
import json
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
        emit('TEST_REPLY '+line+' PLAIN '+plain(json.loads(line.split(' ',2)[2])))
'''


def main():
    repository = Path(__file__).resolve().parents[1]
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
                       'handler':'vanilla_handler','language':'en_us','check_update':False,
                       'advanced_console':False})
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
            send('testchat Alice !!mount switch '+str(target))
            vote_id = wait(r'Alice started switch vote.*Request ([a-f0-9]{32})')[1]
            send('testchat Alice !!mount vote '+vote_id+' yes')
            send('testchat Bob !!mount vote '+vote_id+' yes')
            wait(r'switch request '+vote_id+r'.*Startup verified')
            assert json.loads((root/CONFIG_NAME).read_text())['current_server']==str(target)
            send('!!mount backup')
            wait(r'Server is stopping briefly')
            send('!!MCDR plugin reload mount')
            backup_id = wait(r'backup request .*verified backup ([a-f0-9]{32}).*Startup verified')[1]
            assert (root/'backups'/backup_id/'manifest.json').is_file()
            send('testchat Admin !!mount force reset')
            force_id = wait(r'Force reset:.*Request ([a-f0-9]{32})')[1]
            send('testchat Admin !!mount force confirm '+force_id)
            wait(r'reset request '+force_id+r'.*Startup verified')
            assert (target/'world'/'level.dat').read_bytes()==b'disposable-template'
            assert (target/'world'/'playerdata'/'Alice.dat').read_bytes()==b'player'
            slot_config = json.loads((target/MOUNTABLE_CONFIG).read_text())
            slot_config['reset_type'] = 'full'
            (target/MOUNTABLE_CONFIG).write_text(json.dumps(slot_config))
            send('testchat Admin !!mount force reset')
            force_id = wait(r'Force reset:.*Request ([a-f0-9]{32})')[1]
            send('testchat Admin !!mount force confirm '+force_id)
            wait(r'reset request '+force_id+r'.*Startup verified')
            assert not (target/'world'/'playerdata').exists()
            send('!!MCDR plugin reload mount')
            wait(r'3 of a max of 20 players online')
            send('stop')
            wait(r'bye')
            process.wait(timeout=20)
            assert process.returncode==0
            assert not any('Error loading plugin' in line or 'Error when executing' in line for line in output)
            print('PASS: real MCDR load, snapshot, vote, spaced-path switch, backup, full/region reset, reload during execution, shutdown')
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


if __name__ == '__main__':
    main()
