#!/usr/bin/env python3
"""Exercise the C++ accelerator client against the ARM64 daemon under QEMU."""
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time

root = Path(__file__).resolve().parents[1]
runtime = root / 'out/accelerator-runtime/lib64/rdkhm-accelerator'
client_source = root / 'sources/oh/openharmony-full/drivers/peripheral/nnrt/src/rdkhm_accel_client.cpp'
client_header = root / 'sources/oh/openharmony-full/drivers/peripheral/nnrt/include'
main_source = root / 'tests/nnrt-wire-client.cpp'

with tempfile.TemporaryDirectory(prefix='rdkhm-wire-') as directory:
    temp = Path(directory)
    client = temp / 'nnrt-wire-client'
    subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                    '-I' + str(root / 'bringup/probes'), '-I' + str(client_header),
                    str(client_source), str(main_source), '-o', str(client)], check=True)

    path = temp / 'daemon.sock'
    daemon = subprocess.Popen([
        'qemu-aarch64-static', str(runtime / 'ld-linux-aarch64.so.1'),
        '--inhibit-cache', '--library-path', str(runtime),
        str(runtime / 'accelerator-daemon'), '--socket', str(path)],)
    try:
        for _ in range(200):
            if path.exists():
                probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    probe.connect(str(path))
                    probe.close()
                    break
                except ConnectionRefusedError:
                    probe.close()
            assert daemon.poll() is None, 'daemon exited early'
            time.sleep(.02)
        else:
            raise RuntimeError('daemon socket did not appear')
        result = subprocess.run([str(client), str(path)], text=True, capture_output=True, timeout=30)
        print(result.stdout, end='')
        if result.returncode or 'PASS: accelerator client' not in result.stdout:
            raise RuntimeError(result.stderr or result.stdout or 'client failed')
    finally:
        if daemon.poll() is None:
            daemon.terminate()
            daemon.wait(timeout=3)
print('PASS: C++ wire client framing, status mapping and fd passing')
