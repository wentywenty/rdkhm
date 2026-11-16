#!/usr/bin/env bash
# Import only the documented workspace keys; environment overrides local JSON.
rdkhm_exports=$(python3 - "$workspace" <<'PY'
import shlex
import sys
sys.path.insert(0, sys.argv[1] + '/scripts')
from workspace import KEYS, environment
env = environment()
for key in sorted(KEYS):
    if key in env:
        print('export ' + key + '=' + shlex.quote(env[key]))
PY
) || return $?
eval "$rdkhm_exports"
unset rdkhm_exports
