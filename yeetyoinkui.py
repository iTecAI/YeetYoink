from enum import auto
import eel
from yeetyoink import Connection
import json
import os
import hashlib
import threading

def pformat(path, sep='/'):
    return os.path.join(*path.replace(':', '{{colon}}').split(sep)).replace('{{colon}}', ':')

@eel.expose
def profiles():
    with open('yeetyoink_profiles.json', 'r') as f:
        dat = json.load(f)['profiles']
    return dat

@eel.expose
def write_profiles(_profiles):
    with open('yeetyoink_profiles.json', 'r') as f:
        dat = json.load(f)
    dat['profiles'] = _profiles
    with open('yeetyoink_profiles.json', 'w') as f:
        f.write(json.dumps(dat, indent=4))

@eel.expose
def autoconnect():
    with open('yeetyoink_profiles.json', 'r') as f:
        dat = json.load(f)['autoconnect']
    return dat

@eel.expose
def write_autoconnect(_autoconnect):
    with open('yeetyoink_profiles.json', 'r') as f:
        dat = json.load(f)
    dat['autoconnect'] = _autoconnect
    with open('yeetyoink_profiles.json', 'w') as f:
        f.write(json.dumps(dat, indent=4))

if not os.path.exists('yeetyoink_profiles.json'):
    with open('yeetyoink_profiles.json', 'w') as f:
        f.write(json.dumps({
            'profiles': {},
            'autoconnect': []
        }, indent=4))

CONNECTIONS = {}
cp = profiles()
for a in autoconnect():
    if a in cp.keys():
        CONNECTIONS[a] = Connection(
            cp[a]['network_name'],
            cp[a]['network_key'],
            cp[a]['port'],
            remotes=cp[a]['remotes']
        )

@eel.expose
def new_profile(display_name, network_name, network_key, port, remotes):
    profile = {
        'display_name': display_name,
        'network_name': network_name,
        'network_key': network_key,
        'port': port,
        'remotes': remotes,
        'id': hashlib.sha256(os.urandom(128)).hexdigest()
    }
    profs = profiles()
    profs[profile['id']] = profile.copy()
    write_profiles(profs)
    eel.js_update(profiles())

@eel.expose
def connect(profile_id):
    global CONNECTIONS
    if profile_id in profiles().keys() and not profile_id in CONNECTIONS.keys():
        cp = profiles()
        CONNECTIONS[profile_id] = Connection(
            cp[profile_id]['network_name'],
            cp[profile_id]['network_key'],
            cp[profile_id]['port'],
            remotes=cp[profile_id]['remotes']
        )
        eel.js_update(profiles())
        cur_autocon = autoconnect()
        cur_autocon.append(profile_id)
        write_autoconnect(cur_autocon)

@eel.expose
def disconnect(profile_id):
    global CONNECTIONS
    if profile_id in CONNECTIONS.keys():
        del CONNECTIONS[profile_id]
        eel.js_update(profiles())
        cur_autocon = autoconnect()
        cur_autocon.remove(profile_id)
        write_autoconnect(cur_autocon)

@eel.expose
def list_connections():
    global CONNECTIONS
    return list(CONNECTIONS.keys())

@eel.expose
def remove_profile(profile_id):
    global CONNECTIONS
    profs = profiles()
    if profile_id in profs.keys():
        del profs[profile_id]
    if profile_id in CONNECTIONS.keys():
        del CONNECTIONS[profile_id]
    write_profiles(profs)
    eel.js_update(profiles())

@eel.expose
def list_peers():
    global CONNECTIONS
    peers = []
    for c in CONNECTIONS.keys():
        peers.extend([[i, c, CONNECTIONS[c].node.network]
                      for i in CONNECTIONS[c].enumerate_peers()])
    return peers

@eel.expose
def listdir_local(path):
    try:
        return [[i, os.path.isfile(os.path.join(pformat(path), i))] for i in os.listdir(pformat(path))]
    except:
        return []

@eel.expose
def get_cwd():
    return os.getcwd().replace('\\', '/')

@eel.expose
def listdir_remote(connection, target, path):
    global CONNECTIONS
    if not connection in CONNECTIONS.keys():
        return []
    return CONNECTIONS[connection].listdir(target, directory=path)

def update_yeet(cur, num, yid, lp, rp):
    eel.update_tracker('yeet', yid, cur/num, lp, rp)

def do_yeet(connection, target, local_path, remote_path):
    CONNECTIONS[connection].yeet(
        target,
        local_path,
        remote_path=remote_path,
        callback=update_yeet
    )
    eel.js_update(profiles())

@eel.expose
def yeet(connection, target, local_path, remote_path):
    if not connection in CONNECTIONS.keys():
        return []
    try:
        threading.Thread(target=do_yeet, args=[
                         connection, target, local_path, remote_path]).start()
    except:
        return 'error'

def update_yoink(cur, num, yid, lp, rp):
    eel.update_tracker('yoink', yid, cur/num, lp, rp)

def do_yoink(connection, target, local_path, remote_path):
    CONNECTIONS[connection].yoink(
        target,
        remote_path.strip('/'),
        local_path=local_path.strip('/') + '/' + remote_path.split('/').pop(),
        callback=update_yoink
    )
    eel.js_update(profiles())

@eel.expose
def yoink(connection, target, local_path, remote_path):
    if not connection in CONNECTIONS.keys():
        return []
    try:
        threading.Thread(target=do_yoink, args=[
                         connection, target, local_path, remote_path]).start()
    except:
        return 'error'

@eel.expose
def bonk(connection, target, remote_path):
    if not connection in CONNECTIONS.keys():
        return []
    CONNECTIONS[connection].bonk(target, remote_path)
    eel.js_update(profiles())

@eel.expose
def boop(connection, target, path):
    if not connection in CONNECTIONS.keys():
        return []
    CONNECTIONS[connection].boop(target, path)
    eel.js_update(profiles())

eel.init('static_web')
eel.start('main.html')
