#!/usr/bin/env python3
"""Stage a private glibc process runtime; never install these DSOs into OH search paths."""
import email.parser
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request

WORKSPACE = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.check_output(args, text=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    sources = json.loads((WORKSPACE / 'config/accelerator-sources.json').read_text())
    for name, revision in sources.items():
        target = WORKSPACE / 'sources' / name
        if not target.exists():
            subprocess.run(['git', 'clone', 'https://github.com/D-Robotics/' + name + '.git', str(target)], check=True)
            subprocess.run(['git', '-C', str(target), 'checkout', '--detach', revision], check=True)
        if run('git', '-C', str(target), 'rev-parse', 'HEAD').strip() != revision:
            raise RuntimeError(f'Unexpected revision: {target}')
    downloads = WORKSPACE / 'out/accelerator-downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    lock_path = WORKSPACE / 'config/accelerator-assets-lock.json'
    lock = json.loads(lock_path.read_text())
    if 'libdrm_package' not in lock or lock.get('sources') != sources:
        raise RuntimeError('Missing or inconsistent accelerator lock; review dependency updates explicitly')
    package = downloads / 'libdrm2-arm64.deb'
    if not package.exists():
        urllib.request.urlretrieve(lock['libdrm_package']['url'], package)
    if sha(package) != lock['libdrm_package']['sha256']:
        raise RuntimeError('libdrm package checksum mismatch')
    unpack = downloads / 'libdrm2'
    subprocess.run(['dpkg-deb', '-x', str(package), str(unpack)], check=True)
    dnn = WORKSPACE / 'sources/x5-hobot-dnn/x5/usr/lib'
    multimedia = WORKSPACE / 'sources/x5-hobot-multimedia/debian/usr/hobot/lib'
    directories = [dnn, multimedia, unpack / 'usr/lib/aarch64-linux-gnu', Path('/usr/aarch64-linux-gnu/lib')]
    candidates = {}
    for directory in directories:
        for path in sorted(directory.glob('*.so*')):
            if not path.is_file() or path.read_bytes()[:4] != b'\x7fELF':
                continue
            dynamic = run('readelf', '-d', str(path))
            soname = re.search(r'\(SONAME\).*\[(.*?)\]', dynamic)
            candidates.setdefault(path.name, path)
            if soname:
                candidates.setdefault(soname[1], path)
    stage = WORKSPACE / 'out/accelerator-runtime'
    if stage.exists():
        shutil.rmtree(stage)
    runtime = stage / 'lib64/rdkhm-accelerator'
    runtime.mkdir(parents=True)
    captured = {}
    pending = ['libdnn.so', 'libEGL.so.1', 'libGLESv2.so.2', 'ld-linux-aarch64.so.1']
    while pending:
        name = pending.pop()
        if name in captured:
            continue
        if name not in candidates:
            raise RuntimeError(f'Missing private runtime dependency: {name}')
        path = candidates[name].resolve()
        if 'AArch64' not in run('readelf', '-h', str(path)):
            raise RuntimeError(f'Wrong architecture: {path}')
        captured[name] = {'source': str(path), 'sha256': sha(path)}
        previous = lock.get('libraries', {}).get(name)
        if not previous or previous['sha256'] != captured[name]['sha256']:
            raise RuntimeError(f'Changed runtime asset: {name}')
        shutil.copyfile(path, runtime / name)
        pending.extend(re.findall(r'\(NEEDED\).*\[(.*?)\]', run('readelf', '-d', str(path))))
    if set(captured) != set(lock['libraries']):
        raise RuntimeError('Runtime dependency set differs from pinned lock')
    subprocess.run(['aarch64-linux-gnu-gcc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-O2',
                    '-I' + str(WORKSPACE / 'sources/x5-hobot-dnn/x5/usr/include'),
                    str(WORKSPACE / 'bringup/accelerator-probe.c'), '-ldl', '-o', str(runtime / 'accelerator-probe')], check=True)
    subprocess.run(['aarch64-linux-gnu-gcc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-O2',
                    '-I' + str(WORKSPACE / 'sources/x5-hobot-dnn/x5/usr/include'),
                    str(WORKSPACE / 'bringup/nnrt-worker.c'), '-ldl', '-o', str(runtime / 'nnrt-worker')], check=True)
    subprocess.run(['aarch64-linux-gnu-gcc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-O2',
                    str(WORKSPACE / 'bringup/accelerator-daemon.c'), '-ldl',
                    '-o', str(runtime / 'accelerator-daemon')], check=True)
    thirdparty = WORKSPACE / 'sources/openharmony-full/third_party'
    subprocess.run(['aarch64-linux-gnu-gcc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-O2', '-D__GBM__',
                    '-I' + str(thirdparty / 'EGL/api'), '-I' + str(thirdparty / 'openGLES/api'),
                    '-I' + str(thirdparty / 'mesa3d/src/gbm/main'), str(WORKSPACE / 'bringup/gpu-probe.c'),
                    '-L' + str(runtime), '-Wl,-rpath-link=' + str(runtime),
                    '-l:libEGL.so.1', '-l:libGLESv2.so.2', '-l:libgbm.so.1',
                    '-o', str(runtime / 'gpu-probe')], check=True)
    binaries = stage / 'bin'
    binaries.mkdir()
    shutil.copyfile(WORKSPACE / 'bringup/rdkhm-accelerator.sh', binaries / 'rdkhm-accelerator')
    executables = ['lib64/rdkhm-accelerator/ld-linux-aarch64.so.1',
                   'lib64/rdkhm-accelerator/gpu-probe',
                   'lib64/rdkhm-accelerator/accelerator-probe',
                   'lib64/rdkhm-accelerator/nnrt-worker',
                   'lib64/rdkhm-accelerator/accelerator-daemon', 'bin/rdkhm-accelerator']
    for path in executables:
        (stage / path).chmod(0o755)
    manifest = {'sources': sources, 'executables': executables,
                'files': {str(p.relative_to(stage)): sha(p) for p in stage.rglob('*') if p.is_file()}}
    (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Staged {len(captured)} private AArch64 libraries in {runtime}')


if __name__ == '__main__':
    main()
