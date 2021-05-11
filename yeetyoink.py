import peerbase
import rsa
from cryptography.fernet import Fernet, InvalidToken
import hashlib
import random
import os
import base64
import time
import concurrent.futures
import math
import tempfile


class NonAdvertisingNode(peerbase.Node):
    def launch_advertising_loop(self):
        pass


def pformat(path, sep='/'):
    return os.path.join(*path.replace(':', '{{colon}}').split(sep)).replace('{{colon}}', ':')


class Connection:
    def __init__(self, network, network_key, discovery_port, remotes=None, port_limits=[15000, 60000], blocksize=65536):
        self.node = NonAdvertisingNode(
            hashlib.sha256(str(random.random()).encode('utf-8')).hexdigest(),
            network,
            network_key,
            ports=[random.randint(*port_limits), discovery_port],
            servers=remotes
        )
        (self.public, self.private) = rsa.newkeys(512)
        self.blocksize = blocksize
        self.yeet_meters = {}
        self.yoink_meters = {}
        self.yoinks_in_progress = {}

        self.node.start_multithreaded()

    def enumerate_peers(self):
        targets = list(self.node.peers.keys())
        targets.extend(list(self.node.remote_peers.keys()))
        return list(set(targets))

    def _yeet_single_block(self, yeet_fernet, fd, block, yeet_metadata, target, callback, num_blocks):
        fd.seek(block * self.blocksize)
        blockdata = base64.urlsafe_b64encode(fd.read(self.blocksize))
        block_data = base64.urlsafe_b64encode(
            yeet_fernet.encrypt(
                    base64.urlsafe_b64encode(
                        blockdata
                    )
                )
        )
        try:
            self.node.command(
                command_path='continue_yeet',
                args=[
                    yeet_metadata['yeet_id'],
                    block,
                    block_data.decode('utf-8')
                ],
                target=target, raise_errors=True, timeout=2.5
            )
        except LookupError:
            raise LookupError('Lost connection to target.')
        self.yeet_meters[yeet_metadata['yeet_id']] += 1
        if callable(callback):
            callback(self.yeet_meters[yeet_metadata['yeet_id']], num_blocks)

    def yeet(self, target, local_path, remote_path='', callback=None):
        if not os.path.exists(pformat(local_path)):
            raise FileNotFoundError
        if not os.path.isfile(pformat(local_path)):
            raise IsADirectoryError

        fd = open(pformat(local_path), 'rb')
        fsize = os.path.getsize(pformat(local_path))
        try:
            yeet_metadata = self.node.command(command_path='start_yeet', args=[
                remote_path,
                os.path.split(local_path)[1],
                self.node.name,
                base64.urlsafe_b64encode(
                    self.public.save_pkcs1()).decode('utf-8'),
                math.ceil(fsize / self.blocksize)
            ], target=target, raise_errors=True, timeout=2.5)
        except LookupError:
            raise LookupError(f'Could not locate target {target}.')
        yeet_fernet = Fernet(
            rsa.decrypt(
                base64.urlsafe_b64decode(
                    yeet_metadata['encryption_key'].encode(
                        'utf-8')
                ),
                self.private
            )
        )
        self.yeet_meters[yeet_metadata['yeet_id']] = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = [executor.submit(
                self._yeet_single_block,
                yeet_fernet,
                fd,
                block,
                yeet_metadata,
                target,
                callback,
                math.ceil(fsize / self.blocksize)
            ) for block in range(math.ceil(fsize / self.blocksize))]
        del self.yeet_meters[yeet_metadata['yeet_id']]
        self.node.command(command_path='finish_yeet', args=[
            yeet_metadata['yeet_id']
        ], target=target, raise_errors=True, timeout=2.5)
    
    def _yoink_single_block(self, fernet: Fernet, index, target, yoink_id, callback, num_blocks):
        ret_dat = self.node.command(
            command_path='continue_yoink',
            args=[
                yoink_id,
                index
            ],
            target=target,
            raise_errors=True
        )['data']
        decoded_enced = base64.urlsafe_b64decode(ret_dat.encode('utf-8'))
        decrypted = fernet.decrypt(decoded_enced)
        decoded = base64.urlsafe_b64decode(decrypted)
        self.yoinks_in_progress[yoink_id][index] = tempfile.TemporaryFile()
        self.yoinks_in_progress[yoink_id][index].write(decoded)
        self.yoinks_in_progress[yoink_id][index].seek(0)
        self.yoink_meters[yoink_id] += 1
        if callable(callback):
            callback(self.yoink_meters[yoink_id], num_blocks)
    
    def yoink(self, target, remote_path, local_path=None, callback=None):
        try:
            yoink_metadata = self.node.command(
                command_path='start_yoink',
                args=[
                    remote_path,
                    self.blocksize,
                    base64.urlsafe_b64encode(self.public.save_pkcs1()).decode('utf-8')
                ],
                target=target,
                raise_errors=True
            )
        except LookupError:
            raise LookupError(f'Could not locate target {target}.')
        yoink_fernet = Fernet(
            rsa.decrypt(
                base64.urlsafe_b64decode(
                    yoink_metadata['encryption_key'].encode(
                        'utf-8')
                ),
                self.private
            )
        )

        self.yoink_meters[yoink_metadata['yoink_id']] = 0
        self.yoinks_in_progress[yoink_metadata['yoink_id']] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = [executor.submit(
                self._yoink_single_block,
                yoink_fernet,
                block,
                target,
                yoink_metadata['yoink_id'],
                callback,
                yoink_metadata['blocks']
            ) for block in range(yoink_metadata['blocks'])]
        del self.yoink_meters[yoink_metadata['yoink_id']]
        self.node.command(
            command_path='finish_yoink',
            args=[
                yoink_metadata['yoink_id']
            ],
            target=target,
            raise_errors=True
        )
        if local_path == None:
            assembled_data = []
            for block in range(yoink_metadata['blocks']):
                assembled_data.append(self.yoinks_in_progress[yoink_metadata['yoink_id']][block].read())
            del self.yoinks_in_progress[yoink_metadata['yoink_id']]
            return b''.join(assembled_data)
        else:
            try:
                os.makedirs(os.path.split(pformat(local_path))[0], exist_ok=True)
            except:
                pass
            with open(pformat(local_path), 'wb') as f:
                for block in range(yoink_metadata['blocks']):
                    f.write(self.yoinks_in_progress[yoink_metadata['yoink_id']][block].read())
            del self.yoinks_in_progress[yoink_metadata['yoink_id']]
            return pformat(local_path)
    
    def listdir(self, target, directory=''):
        return self.node.command(
            command_path='listfiles',
            kwargs={
                'path': directory
            },
            target=target,
            raise_errors=True
        )
    
    def walk(self, target, top=''):
        return self.node.command(
            command_path='walk',
            kwargs={
                'path': top
            },
            target=target,
            raise_errors=True
        )
    
    def boop(self, target, path): # Make new folder
        return self.node.command(
            command_path='boop',
            kwargs={
                'path': path
            },
            target=target,
            raise_errors=True
        )
    
    def bonk(self, target, path): # Delete a file or folder
        self.node.command(
            command_path='bonk',
            kwargs={
                'path': path
            },
            target=target,
            raise_errors=True
        )

