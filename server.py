from json.decoder import JSONDecodeError
from peerbase import Node
import json
import argparse
from cryptography.fernet import Fernet, InvalidToken
from socket import *
import os
import shutil
import sys
import logging
import collections.abc, collections
import random, hashlib
import base64
import rsa
import time
import threading
import tempfile
import math

class YeetNotFoundError(KeyError):
    pass

class YoinkNotFoundError(KeyError):
    pass

def pformat(path, sep='/'):
    return os.path.join(*path.replace(':', '{{colon}}').split(sep)).replace('{{colon}}', ':')

def tupperware(mapping):
    if isinstance(mapping, collections.abc.Mapping):
        for key, value in mapping.items():
            mapping[key] = tupperware(value)
        return namedtuple_from_mapping(mapping)
    return mapping


def namedtuple_from_mapping(mapping, name="Config"):
    this_namedtuple_maker = collections.namedtuple(name, mapping.keys())
    return this_namedtuple_maker(**mapping)

parser = argparse.ArgumentParser(description='Start YeetYoink server. Should be run on system boot for best results.')
parser.add_argument('config', type=str, help='Path to config JSON file. REQUIRED.')
parser.add_argument('--loglevel', type=str, default="info", help="Name of logging level to use. Defaults to 'info'.")

args = parser.parse_args()

if type(logging.getLevelName(args.loglevel.upper())) == int:
    logging.basicConfig(format='%(filename)s:%(lineno)s:%(levelname)s @ %(asctime)s > %(message)s', level=logging.getLevelName(args.loglevel.upper()))
else:
    logging.basicConfig(format='%(filename)s:%(lineno)s:%(levelname)s @ %(asctime)s > %(message)s', level=logging.INFO)

if os.path.exists(args.config):
    with open(args.config, 'r') as f:
        try:
            CONFIG = tupperware(json.load(f))
        except JSONDecodeError:
            logging.critical(f'Failed to load config file @ "{args.config}" due to bad JSON.')
            sys.exit()
else:
    logging.critical(f'Config file "{args.config}" could not be located.')
    sys.exit()

NODE = Node(
    CONFIG.node.name.replace('.','-').replace('|','-').replace(':','-').format(hostname=gethostname(), ipaddr=gethostbyname(gethostname())), 
    CONFIG.node.network.replace('.','-').replace('|','-').replace(':','-'), 
    CONFIG.node.network_key, 
    ports=[
        CONFIG.node.node_port,
        CONFIG.node.advertiser_port
    ], 
    servers=CONFIG.node.relays
)

class State:
    def __init__(self):
        self.yeets = {}
        self.yoinks = {}

STATE = State()

def check_timeouts_loop():
    global STATE
    while True:
        for yeet in list(STATE.yeets.keys()):
            if STATE.yeets[yeet]['timeout_time'] < time.time():
                [x.close() for x in STATE.yeets[yeet]['data'].values()]
                del STATE.yeets[yeet]
        for yoink in list(STATE.yoinks.keys()):
            if STATE.yoinks[yoink]['timeout_time'] < time.time():
                STATE.yoinks[yoink]['file_object'].close()
                del STATE.yoinks[yoink]
        time.sleep(0.5)

if (
    os.path.exists(os.path.join(pformat(CONFIG.security.certificate_folder), 'public.pem')) and 
    os.path.exists(os.path.join(pformat(CONFIG.security.certificate_folder), 'private.pem'))
):
    logging.info('Loading RSA keys from file.')
    with open(os.path.join(pformat(CONFIG.security.certificate_folder), 'public.pem'), 'rb') as f:
        pubkey = rsa.PublicKey.load_pkcs1(f.read())
    with open(os.path.join(pformat(CONFIG.security.certificate_folder), 'private.pem'), 'rb') as f:
        privkey = rsa.PrivateKey.load_pkcs1(f.read())
else:
    logging.info('Generating new RSA keys.')
    (pubkey, privkey) = rsa.newkeys(512)
    with open(os.path.join(pformat(CONFIG.security.certificate_folder), 'public.pem'), 'wb') as f:
        f.write(pubkey.save_pkcs1())
    with open(os.path.join(pformat(CONFIG.security.certificate_folder), 'private.pem'), 'wb') as f:
        f.write(privkey.save_pkcs1())


logging.info(f'Initialized new node {NODE.name} in {NODE.network}. \n\tPorts: {str(NODE.ports)}')
logging.info(f'Virtual Filesystem Root: {pformat(CONFIG.transfer.root)}')

logging.debug('Registering commands')
def get_node_info(node: Node, args: list, kwargs: dict):
    return {
        'role': 'server',
        'name': node.name
    }
NODE.register_command('node_info', get_node_info)

def list_files(node: Node, args: list, kwargs: dict):
    if 'path' in kwargs.keys():
        fpath = os.path.join(pformat(CONFIG.transfer.root), pformat(kwargs['path']))
        if os.path.exists(fpath):
            if os.path.isdir(fpath):
                return [[f, os.path.isfile(os.path.join(fpath, f))] for f in os.listdir(fpath)]
            else:
                raise NotADirectoryError(f'Path "{kwargs["path"]}" is not a directory.')
        else:
            raise FileNotFoundError(f'Could not find a directory at path "{kwargs["path"]}".')
    else:
        return [[f, os.path.isfile(os.path.join(pformat(CONFIG.transfer.root), f))] for f in os.listdir(pformat(CONFIG.transfer.root))]
NODE.register_command('listfiles', list_files)

def start_yeet_recv(node: Node, args: list, kwargs: dict): # path, filename, node_name, public_key, num_blocks
    if len(args) < 5:
        raise TypeError('5 positional arguments are required.')
    yeet_id = hashlib.sha256(str(random.random()).encode('utf-8')).hexdigest()
    logging.info(f'Receiving YEET with ID {yeet_id} from {args[2]}. Peer YEETing to {args[0]}/{args[1]}')
    yeet_enc = Fernet.generate_key()
    STATE.yeets[yeet_id] = {
        'path': args[0],
        'filename': args[1],
        'originator': args[2],
        'originator_key': rsa.PublicKey.load_pkcs1(base64.urlsafe_b64decode(args[3].encode('utf-8'))),
        'data': {},
        'encryption_key': yeet_enc,
        'fernet_instance': Fernet(yeet_enc),
        'num_blocks': args[4],
        'timeout_time': time.time() + CONFIG.transfer.file_timeout
    }
    return {
        'yeet_id': yeet_id,
        'encryption_key': base64.urlsafe_b64encode(rsa.encrypt(STATE.yeets[yeet_id]['encryption_key'], STATE.yeets[yeet_id]['originator_key'])).decode('utf-8')
    }
NODE.register_command('start_yeet', start_yeet_recv)

def continue_yeet(node: Node, args: list, kwargs: dict): # yeet id, block index, block
    if len(args) < 3:
        raise TypeError('3 positional arguments are required.')
    if not args[0] in STATE.yeets.keys():
        raise YeetNotFoundError(f'YEET {args[0]} does not exist.')
    logging.debug(f'Continuing YEET {args[0]} @ Block Index {str(args[1])}.')
    try:
        b64_layer_i = base64.urlsafe_b64decode(args[2].encode('utf-8'))
    except:
        raise TypeError('Failed to decode block base64.')
    try:
        dec_layer = STATE.yeets[args[0]]['fernet_instance'].decrypt(b64_layer_i)
    except InvalidToken:
        raise InvalidToken('Failed to decrypt decoded base64 block.')
    try:
        decoded = base64.urlsafe_b64decode(dec_layer)
    except:
        raise TypeError('Failed to decode decrypted data base64.')
    if args[1] in STATE.yeets[args[0]]['data'].keys():
        raise IndexError(f'Block at index {str(args[1])} already exists')
    STATE.yeets[args[0]]['timeout_time'] = time.time() + CONFIG.transfer.file_timeout
    STATE.yeets[args[0]]['data'][args[1]] = tempfile.TemporaryFile()
    STATE.yeets[args[0]]['data'][args[1]].write(decoded)
    STATE.yeets[args[0]]['data'][args[1]].seek(0)
    return {
        'state': 'in progress',
        'remaining_blocks': STATE.yeets[args[0]]['num_blocks'] - len(STATE.yeets[args[0]]['data'].keys())
    }
NODE.register_command('continue_yeet', continue_yeet)

def finish_yeet_spinoff(args):
    if not os.path.exists(os.path.join(pformat(CONFIG.transfer.root), pformat(STATE.yeets[args[0]]['path']))):
        os.makedirs(os.path.join(pformat(CONFIG.transfer.root), pformat(STATE.yeets[args[0]]['path'])), exist_ok=True)
    with open(os.path.join(pformat(CONFIG.transfer.root), pformat(STATE.yeets[args[0]]['path']), STATE.yeets[args[0]]['filename']), 'wb') as f:
        for i in range(len(STATE.yeets[args[0]]['data'].keys())):
            STATE.yeets[args[0]]['timeout_time'] = time.time() + CONFIG.transfer.file_timeout
            f.write(base64.urlsafe_b64decode(STATE.yeets[args[0]]['data'][i].read()))
            STATE.yeets[args[0]]['data'][i].close()
            del STATE.yeets[args[0]]['data'][i]
    del STATE.yeets[args[0]]

def finish_yeet(node: Node, args: list, kwargs: dict):
    if len(args[0]) == 0:
        raise TypeError('1 positional argument is required.')
    logging.info(f'Finished YEET {args[0]}.')
    threading.Thread(target=finish_yeet_spinoff, args=[args, ]).start()
    return {
        'state': 'complete',
        'remaining_blocks': 0
    }
NODE.register_command('finish_yeet', finish_yeet)

def start_yoink(node: Node, args: list, kwargs: dict): # server path, blocksize, public key
    if len(args) < 3:
        raise TypeError('3 positional arguments are required.')
    rpath = os.path.join(pformat(CONFIG.transfer.root), pformat(args[0]))
    if os.path.exists(rpath):
        if os.path.isdir(rpath):
            raise IsADirectoryError
    else:
        raise FileNotFoundError
    yoink_id = hashlib.sha256(str(random.random()).encode('utf-8')).hexdigest()
    logging.info(f'Starting YOINK with ID {yoink_id} from path args[0]')
    yoink_enc = Fernet.generate_key()
    STATE.yoinks[yoink_id] = {
        'path': args[0],
        'originator_key': rsa.PublicKey.load_pkcs1(base64.urlsafe_b64decode(args[2].encode('utf-8'))),
        'file_object': open(rpath, 'rb'),
        'encryption_key': yoink_enc,
        'fernet_instance': Fernet(yoink_enc),
        'timeout_time': time.time() + CONFIG.transfer.file_timeout,
        'blocksize': args[1]
    }
    return {
        'yoink_id': yoink_id,
        'encryption_key': base64.urlsafe_b64encode(rsa.encrypt(STATE.yoinks[yoink_id]['encryption_key'], STATE.yoinks[yoink_id]['originator_key'])).decode('utf-8'),
        'blocks': math.ceil(os.path.getsize(rpath) / args[1])
    }
NODE.register_command('start_yoink', start_yoink)

def continue_yoink(node: Node, args: list, kwargs: dict): # yoink ID, block index
    if len(args) < 2:
        raise TypeError('2 positional arguments are required.')
    if not args[0] in STATE.yoinks.keys():
        raise YoinkNotFoundError(f'YOINK {args[0]} does not exist.')
    logging.debug(f'Continuing YOINK {args[0]} @ Block Index {str(args[1])}.')
    STATE.yoinks[args[0]]['timeout_time'] = time.time() + CONFIG.transfer.file_timeout
    STATE.yoinks[args[0]]['file_object'].seek(args[1] * STATE.yoinks[args[0]]['blocksize'])
    raw_data = STATE.yoinks[args[0]]['file_object'].read(STATE.yoinks[args[0]]['blocksize'])
    raw_data_b64_1 = base64.urlsafe_b64encode(raw_data)
    encrypted_b64_1 = STATE.yoinks[args[0]]['fernet_instance'].encrypt(raw_data_b64_1)
    encoded_data = base64.urlsafe_b64encode(encrypted_b64_1).decode('utf-8')
    return {
        'start_position': args[1] * STATE.yoinks[args[0]]['blocksize'],
        'data': encoded_data
    }
NODE.register_command('continue_yoink', continue_yoink)

def finish_yoink(node: Node, args: list, kwargs: dict):
    if len(args) < 1:
        raise TypeError('1 positional arguments are required.')
    if not args[0] in STATE.yoinks.keys():
        raise YoinkNotFoundError(f'YOINK {args[0]} does not exist.')
    logging.info(f'Finished YOINK {args[0]}.')
    STATE.yoinks[args[0]]['file_object'].close()
    del STATE.yoinks[args[0]]
    return {}
NODE.register_command('finish_yoink', finish_yoink)

def walk(node: Node, args: list, kwargs: dict):
    if 'path' in kwargs:
        walk_data = list(os.walk(os.path.join(pformat(CONFIG.transfer.root), pformat(kwargs['path']))))
    else:
        walk_data = list(os.walk(pformat(CONFIG.transfer.root)))
    processed = []
    for d in walk_data:
        processed.append([d[0].split(pformat(CONFIG.transfer.root))[1].replace('\\', '/').lstrip('/'), d[1], d[2]])
    return processed
NODE.register_command('walk', walk)

def boop(node: Node, args: list, kwargs: dict): # Creates a new folder
    if 'path' in kwargs.keys():
        logging.info(f'BOOPing {kwargs["path"]}')
        os.makedirs(os.path.join(pformat(CONFIG.transfer.root), pformat(kwargs['path'])), exist_ok=True)
        return kwargs['path']
    else:
        raise TypeError('kwargs must include path of new folder.')
NODE.register_command('boop', boop)

def bonk(node: Node, args: list, kwargs: dict): # Delete file or folder
    if 'path' in kwargs.keys():
        path = os.path.join(pformat(CONFIG.transfer.root), pformat(kwargs['path']))
        logging.info(f'BONKing {kwargs["path"]}')
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        else:
            raise FileNotFoundError
    else:
        raise TypeError('kwargs must include path of new folder.')
NODE.register_command('bonk', bonk)

logging.info('Starting timeout check thread.')
check_thread = threading.Thread(name='check_timeouts', target=check_timeouts_loop, daemon=True)
check_thread.start()

logging.info('Starting node.')
try:
    NODE.start_multithreaded()
    while True:
        pass
except KeyboardInterrupt:
    sys.exit()