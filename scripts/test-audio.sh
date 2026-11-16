#!/usr/bin/env bash
set -euo pipefail
workspace=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$workspace/out/tests"
cc -std=gnu11 -Wall -Wextra -Werror -fsanitize=address,undefined -g \
  -I"$workspace/tests/audio" \
  -I"$workspace/overlay/device/board/drobotics/rdk_x5/audio_alsa" \
  "$workspace/tests/audio/test_x5_audio.c" -lasound \
  -o "$workspace/out/tests/test-x5-audio"
"$workspace/out/tests/test-x5-audio"
