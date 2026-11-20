#!/usr/bin/env python3
"""Create an isolated, pinned WS73 SDK and generate its missing autoconfig header."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from workspace import environment

WORKSPACE = Path(__file__).resolve().parents[1]
ENV = environment()
REFERENCE = Path(ENV.get('RDKHM_NEARLINK_REFERENCE', str(WORKSPACE / 'thirdparty/reference-nearlink')))
REVISION = 'bcbd3ecf5bc407a2bd44e9dd5187c054124e9d79'
SDK_PATH = 'assets/sdk/ws73_sdk_linux_WS73_1.10.110'
# repo.xml keeps these generated trees beside the OH and kernel checkouts.
OH_ROOT = Path(ENV['RDKHM_OH_TREE']).parent
RDK_ROOT = Path(ENV['RDKHM_KERNEL_TREE']).parent


def main():
    stack = OH_ROOT / 'nearlink-ssap'
    if not stack.exists():
        stack.mkdir(parents=True)
        with tempfile.TemporaryFile() as archive:
            subprocess.run(['git', '-C', str(REFERENCE), 'archive', REVISION, 'assets/stack/ssap'],
                           stdout=archive, check=True)
            archive.seek(0)
            subprocess.run(['tar', '-x', '--strip-components=3', '-C', str(stack)], stdin=archive, check=True)
        (stack / '.rdkhm-source.json').write_text(json.dumps({'reference': str(REFERENCE), 'revision': REVISION}))
        subprocess.run(['git', 'init', '-q', str(stack)], check=True)
        subprocess.run(['git', '-C', str(stack), 'add', 'Makefile', 'include', 'src', 'test'], check=True)
    if json.loads((stack / '.rdkhm-source.json').read_text())['revision'] != REVISION:
        raise RuntimeError('Unexpected SSAP source revision')
    for patch in sorted((WORKSPACE / 'patches/nearlink-ssap').glob('*.patch')):
        reverse = subprocess.run(['git', '-C', str(stack), 'apply', '--reverse', '--check', str(patch)],
                                 capture_output=True)
        if reverse.returncode:
            subprocess.run(['git', '-C', str(stack), 'apply', '--check', str(patch)], check=True)
            subprocess.run(['git', '-C', str(stack), 'apply', str(patch)], check=True)
    link = WORKSPACE / 'overlay/device/board/drobotics/rdk_x5/nearlink/ssap'
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() and link.resolve() != stack.resolve():
        link.unlink()
    if not link.exists():
        link.symlink_to(os.path.relpath(stack, link.parent), target_is_directory=True)
    sdk = RDK_ROOT / 'ws73-sdk'
    if not sdk.exists():
        sdk.mkdir(parents=True)
        with tempfile.TemporaryFile() as archive:
            subprocess.run(['git', '-C', str(REFERENCE), 'archive', REVISION, SDK_PATH],
                           stdout=archive, check=True)
            archive.seek(0)
            subprocess.run(['tar', '-x', '--strip-components=3', '-C', str(sdk)], stdin=archive, check=True)
        subprocess.run(['git', 'init', '-q', str(sdk)], check=True)
        subprocess.run(['git', '-C', str(sdk), 'add', '-f', '.'], check=True)
        (sdk / '.rdkhm-source.json').write_text(json.dumps({'reference': str(REFERENCE), 'revision': REVISION}))
    source = json.loads((sdk / '.rdkhm-source.json').read_text())
    if source['revision'] != REVISION:
        raise RuntimeError('Unexpected WS73 source revision')
    # This SDK snapshot omits Kconfig. Preserve its explicit config values and
    # reject unknown syntax rather than inventing defaults for missing symbols.
    values = {}
    for line in (sdk / '.config').read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z_][A-Za-z_0-9]*)=(y|n|m|-?[0-9]+|0x[0-9A-Fa-f]+|"[^"\n]*")', line)
        if not match:
            raise RuntimeError(f'Unsupported SDK config: {line}')
        values[match[1]] = match[2]
    cross = ENV.get('CROSS_COMPILE', 'aarch64-none-linux-gnu-')
    compiler_include = subprocess.check_output(
        [cross + 'gcc', '-print-file-name=include'], text=True).strip()
    if not Path(compiler_include).is_dir():
        raise RuntimeError(f'Missing compiler builtin headers: {compiler_include}')
    values.update({
        'WSCFG_USING_GCC': 'y',
        'WSCFG_CROSS_COMPILE': json.dumps(cross),
        'WSCFG_EXTRA_CFLAGS': json.dumps(f'-Wno-error -I{compiler_include}'),
        'WSCFG_ARCH_ARM': 'n', 'WSCFG_ARCH_CUSTOM': 'y', 'WSCFG_ARCH_NAME': '"arm64"',
        'WSCFG_KERNEL_DIR': json.dumps(str(WORKSPACE / 'out/kernel/obj')),
        'CONFIG_FIRMWARE_BIN_PATH': '"/vendor/etc/firmware/ws73/ws73.bin"',
        'CONFIG_FIRMWARE_WIFICALI_PATH': '"/vendor/etc/firmware/ws73/wifi_cali.bin"',
        'CONFIG_FIRMWARE_BSLECALI_PATH': '"/vendor/etc/firmware/ws73/btc_cali.bin"',
        'CONFIG_FIRMWARE_WOW_PATH': '"/vendor/etc/firmware/ws73/wow.bin"',
        'CONFIG_INI_FILE_PATH': '"/vendor/etc/ws73_cfg.ini"',
    })
    output = WORKSPACE / 'out/nearlink'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'ws73.config').write_text(''.join(f'{k}={v}\n' for k, v in values.items() if v != 'n'))
    (output / 'autoconfig.h').write_text('/* Generated from pinned WS73 config plus X5 overrides. */\n' +
        ''.join(f'#define {k} {"1" if v == "y" else v}\n' for k, v in values.items() if v != 'n'))
    print(f'Prepared {sdk}, source {REVISION}')
    required = ['Kconfig', 'driver/platform/ws73_comm_defconfig',
                'driver/platform/plat_ws73_default_defconfig',
                'driver/wifi/ws73_comm_defconfig', 'driver/wifi/ws73_wifi_defconfig',
                'firmware/us/ws73.bin', 'firmware/us/wifi_cali.bin', 'firmware/us/btc_cali.bin']
    missing = [p for p in required if not (sdk / p).is_file()]
    (output / 'preflight.json').write_text(json.dumps({'source_revision': REVISION, 'missing': missing}, indent=2) + '\n')
    if missing:
        print('Incomplete SDK; kernel driver/firmware integration pending: ' + ', '.join(missing))


if __name__ == '__main__':
    main()
