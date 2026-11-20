#!/usr/bin/env python3
"""Exercise the staged ARM64 daemon through its private loader under QEMU."""
import array
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import time

root = Path(__file__).resolve().parents[1]
runtime = root / 'out/accelerator-runtime/lib64/rdkhm-accelerator'
command = ['qemu-aarch64-static', str(runtime / 'ld-linux-aarch64.so.1'),
           '--inhibit-cache', '--library-path', str(runtime), str(runtime / 'accelerator-daemon')]

with tempfile.TemporaryDirectory(prefix='rdkhm-socket-') as directory:
    path = directory + '/listener'
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(path)
    # OH init may hand over a bound socket before listen().
    env = dict(os.environ, OHOS_SOCKET_rdkhm_accel=str(listener.fileno()))
    process = subprocess.Popen(command, env=env, pass_fds=(listener.fileno(),))

    def connect():
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(4)
        client.connect(path)
        return client

    def request(parts, expected):
        with connect() as client:
            for part in parts:
                client.sendall(part)
                time.sleep(.02)
            data = b''
            while not data.endswith(b'\n'):
                chunk = client.recv(256)
                assert chunk, data
                data += chunk
            assert data == expected, data

    try:
        for attempt in range(100):
            try:
                with connect():
                    break
            except ConnectionRefusedError:
                assert process.poll() is None
                time.sleep(.02)
        request([b'PI', b'NG\n'], b'PONG\n')
        with connect() as client:
            for text_command, expected in ((b'PING\n', b'PONG\n'),
                                           (b'GPU_COMPOSE_CHECK\n', b'GPU_COMPOSE_UNAVAILABLE\n')):
                client.sendall(text_command)
                data = b''
                while not data.endswith(b'\n'):
                    chunk = client.recv(256)
                    assert chunk, data
                    data += chunk
                assert data == expected, data
        request([b'PING\r\n'], b'PONG\n')
        request([b'PING\0\n'], b'ERROR invalid-frame\n')
        request([b'x' * 128], b'ERROR invalid-frame\n')
        MAGIC = 0x314B4452
        VERSION = 1

        def binary(sock, command, session=0, payload=b'', fds=()):
            header = struct.pack('<IHHIIHHI', MAGIC, VERSION, command, session,
                                 len(payload), len(fds), 0, 0)
            if fds:
                rights = array.array('i', fds)
                sock.sendmsg([header], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, rights)])
            else:
                sock.sendall(header)
            if payload:
                sock.sendall(payload)
            data = b''
            while len(data) < 24:
                chunk = sock.recv(24 - len(data))
                assert chunk, data
                data += chunk
            magic, version, got, session, length, fd_count, _, _ = struct.unpack('<IHHIIHHI', data)
            assert (magic, version, got, fd_count) == (MAGIC, VERSION, command, 0), data
            body = b''
            while len(body) < length:
                chunk = sock.recv(length - len(body))
                assert chunk, body
                body += chunk
            return session, body

        with connect() as client:
            session, body = binary(client, 1)
            assert struct.unpack('<I', body)[0] == 0, body
        with connect() as client:
            _, body = binary(client, 3, session=999)
            assert struct.unpack('<I', body)[0] == 31, body
        with connect() as client:
            _, body = binary(client, 5, session=999)
            assert struct.unpack('<I', body)[0] == 31, body
        with connect() as client:
            load_request = struct.pack('<II', 0, 0)
            _, body = binary(client, 2, payload=load_request)
            assert struct.unpack('<I', body)[0] == 31, body
        with connect() as client:
            _, body = binary(client, 6, payload=b'')
            assert struct.unpack('<I', body)[0] == 3, body
        model = os.memfd_create('empty-model')
        try:
            with connect() as client:
                _, body = binary(client, 2, fds=(model,))
                assert struct.unpack('<I', body)[0] == 31, body
        finally:
            os.close(model)
        request([b'GPU_COMPOSE_CHECK\n'], b'GPU_COMPOSE_UNAVAILABLE\n')
        request([b'NNRT_BACKEND\n'], b'NNRT_BACKEND_RUNTIME_READY\n')
        with connect() as idle:
            assert idle.recv(256) == b'ERROR timeout\n'
        request([b'PING\n'], b'PONG\n')
        with connect() as idle:
            time.sleep(.05)
            process.terminate()
            assert process.wait(timeout=3) == 0
        assert Path(path).exists(), 'daemon removed init-owned socket'
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        listener.close()
    env['OHOS_SOCKET_rdkhm_accel'] = 'invalid'
    assert subprocess.run(command, env=env, timeout=3).returncode != 0
print('PASS: ARM64 inherited socket, fragmented frames, bounds, timeout, shutdown and invalid fd')
