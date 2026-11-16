#!/usr/bin/env python3
"""Exercise the staged ARM64 daemon through its private loader under QEMU."""
import os
from pathlib import Path
import socket
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
        request([b'PING\r\n'], b'PONG\n')
        request([b'PING\0\n'], b'ERROR invalid-frame\n')
        request([b'x' * 128], b'ERROR invalid-frame\n')
        request([b'NNRT_BACKEND\n'], b'NNRT_BACKEND_UNAVAILABLE\n')
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
