#!/usr/bin/env python3
"""Check the isolated ARM64 runtime without opening an accelerator or loading a model."""
import json
from pathlib import Path
import re
import subprocess

from workspace import environment

workspace = Path(__file__).resolve().parents[1]
env = environment()
runtime = workspace / 'out/accelerator-runtime/lib64/rdkhm-accelerator'
obj = workspace / 'out/kernel/obj'
for executable in ('nnrt-worker', 'accelerator-daemon', 'gpu-probe', 'gpu-compose-test', 'accel-compose-client'):
    if not (runtime / executable).is_file() or not (runtime / executable).stat().st_mode & 0o111:
        raise RuntimeError(f'{executable} is not executable')
if 'CONFIG_VERISILICON_X5_SYSCON_BRIDGE=y\n' not in (obj / '.config').read_text():
    raise RuntimeError('Display bridge must be built in for early OH boot')
undefined = subprocess.check_output(['aarch64-linux-gnu-nm', '-u',
                                    str(obj / 'drivers/gpu/drm/verisilicon/vs_drv.o')], text=True)
if 'request_module' in undefined:
    raise RuntimeError('Built-in DRM still depends on early userspace modprobe')
for path in runtime.iterdir():
    if path.read_bytes()[:4] != b'\x7fELF':
        continue
    dynamic = subprocess.check_output(['readelf', '-d', str(path)], text=True)
    for name in re.findall(r'\(NEEDED\).*\[(.*?)\]', dynamic):
        if not (runtime / name).is_file():
            raise RuntimeError(f'Private dependency missing: {path.name} -> {name}')
command = ['qemu-aarch64-static', str(runtime / 'ld-linux-aarch64.so.1'),
           '--inhibit-cache', '--library-path', str(runtime), str(runtime / 'accelerator-probe')]
result = subprocess.run([*command, '--check'], text=True, capture_output=True, check=True, timeout=30)
print(result.stdout, end='')
if 'LIBRARY_CHECK_PASS' not in result.stdout or 'DNN_VERSION 1.24.5' not in result.stdout:
    raise RuntimeError('Unexpected accelerator runtime response')
invalid = subprocess.run([*command, '--invalid'], capture_output=True, timeout=30)
if invalid.returncode != 2:
    raise RuntimeError('Invalid command did not fail')
descriptor = subprocess.run(
    ['qemu-aarch64-static', str(runtime / 'ld-linux-aarch64.so.1'), '--inhibit-cache',
     '--library-path', str(runtime), str(runtime / 'nnrt-worker'), '--describe', '/dev/null'],
    capture_output=True, text=True, timeout=30)
if descriptor.returncode == 0 or 'MODEL LOAD FAILED' not in descriptor.stderr:
    raise RuntimeError('NNRT descriptor worker did not reject an invalid model')
lock = json.loads((workspace / 'config/accelerators/assets-lock.json').read_text())
# libGLSLC.so is dlopen'ed when the first GL context is created, so it is not
# part of the ELF NEEDED closure above; its absence surfaces as EGL_BAD_CONFIG.
if not (runtime / 'libGLSLC.so').is_file():
    raise RuntimeError('Missing libGLSLC.so; eglCreateContext will fail')
if 'libGLSLC.so' not in lock['libraries']:
    raise RuntimeError('libGLSLC.so is not pinned in the accelerator asset lock')
gal = Path(lock['libraries']['libGAL.so']['source']).read_bytes()
header = (Path(env['RDKHM_KERNEL_TREE']) /
          'drivers/misc/verisilicon/gc8000l/hal/kernel/inc/gc_hal_version.h').read_text()
version = [re.search(r'#define gcvVERSION_' + name + r'\s+(\d+)', header)[1]
           for name in ('MAJOR', 'MINOR', 'PATCH', 'BUILD')]
marker = f'$VERSION${".".join(version[:3])}:{version[3]}$'.encode()
if marker not in gal:
    raise RuntimeError('GPU kernel/userspace version marker mismatch')
print('PASS: private dependency closure, ARM64 library loading, DNN version and GPU version markers')
print('PASS: accelerator daemon executable is staged (socket behavior tested separately)')
print('NOT TESTED: hardware rendering, model execution, OH RenderService or NNRT integration')
