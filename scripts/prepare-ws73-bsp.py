#!/usr/bin/env python3
"""Import the pinned RoboParty BSP SDK into an isolated X5 build tree."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from workspace import environment

root = Path(__file__).resolve().parents[1]
env = environment()
bsp = Path(env.get('RDKHM_BSP', str(root / 'sources/reference-bsp')))
archive = Path(env.get('RDKHM_WS73_ARCHIVE', str(bsp / 'packages/blobs/ws73/ws73_sdk_linux_WS73_1.10.110_patched.tar.gz')))
expected = '94a02d3a8031482827ebf323261ac596b8c2b63c10e0188f6f58beefa2f18f65'
if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
    raise RuntimeError('WS73 BSP archive checksum mismatch')
sdk = root / 'sources/ws73-bsp-94a02d3a'
marker = sdk / '.rdkhm-source.json'
if not sdk.exists():
    sdk.mkdir(parents=True)
    subprocess.run(['tar', '-xzf', str(archive), '-C', str(sdk)], check=True)
    marker.write_text(json.dumps({'archive': str(archive), 'sha256': expected}, indent=2) + '\n')
if json.loads(marker.read_text())['sha256'] != expected:
    raise RuntimeError('Unexpected WS73 BSP source')
if not (sdk / '.git').exists():
    subprocess.run(['git', 'init', '-q', str(sdk)], check=True)
for patch in sorted((root / 'patches/nearlink-bsp').glob('*.patch')):
    reverse = subprocess.run(['git', 'apply', '--reverse', '--check', str(patch)], cwd=sdk, capture_output=True)
    if reverse.returncode:
        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=sdk, check=True)
        subprocess.run(['git', 'apply', str(patch)], cwd=sdk, check=True)
cross = env.get('CROSS_COMPILE', 'aarch64-none-linux-gnu-')
overrides = {
    'WSCFG_CROSS_COMPILE': json.dumps(cross),
    'WSCFG_KERNEL_DIR': json.dumps(str(root / 'out/kernel/obj')),
    'WSCFG_ARCH_NAME': '"arm64"',
    'WSCFG_ARCH_ARM': 'n', 'WSCFG_ARCH_CUSTOM': 'y',
    'CONFIG_INI_FILE_PATH': '"/vendor/etc/ws73_cfg.ini"',
}
for key, name in [('BIN', 'ws73'), ('WIFICALI', 'wifi_cali'), ('BSLECALI', 'btc_cali'), ('WOW', 'wow')]:
    overrides[f'CONFIG_FIRMWARE_{key}_PATH'] = json.dumps(f'/vendor/etc/firmware/ws73/{name}.bin')
lines = []
for line in (sdk / 'build/config/ws73_usb_light_v2.config').read_text().splitlines():
    match = re.fullmatch(r'(\w+)=.*|# (\w+) is not set', line)
    key = (match[1] or match[2]) if match else None
    if key in overrides:
        value = overrides.pop(key)
        line = f'# {key} is not set' if value == 'n' else f'{key}={value}'
    lines.append(line)
if overrides:
    raise RuntimeError(f'Unknown WS73 config keys: {list(overrides)}')
(sdk / '.config').write_text('\n'.join(lines) + '\n')
print(sdk)
