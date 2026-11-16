# Boot and audio fixes, 2026-11-16

## Causes

- StorageDaemon failed to create `/data/service/el3/100` because its parent was
  missing. Single-stage init also omitted EL4 service and EL5 app/service roots.
- Account creation then remained incomplete. Empty indexes serialized as
  `null`, which the account file reader rejects as unstructured JSON.
- Audio crash PC `libsink_adapter.z.so+0xf988` resolves to sink_adapter.cpp:97.
  The optional aux pointer was null. Two local SinkAdapterAttr objects also
  lacked initialization.
- The driver bundle omitted designware_i2s. The sound card remained deferred.

## Changes

Product post-fs-data creates the missing roots. Account indexes use objects.
Audio accepts omitted aux as an empty string and zero-initializes attributes.
The bundle loads designware_i2s before the machine driver.

Replay source changes with `scripts/prepare-openharmony.sh`.
Run `python3 tests/test-boot-audio-regressions.py` for production-function tests.
Both account and audio sources compile in the complete images target.

## Live evidence

Backups: `/data/rdkhm-fixes/boot-audio-20261116-201121/original`.
Earlier pre-deployment backups also exist under `boot-audio-20261116-201026`.
The first replacement attempt encountered a read-only root. The second attempt
remounted it temporarily and verified all installed library hashes.
The deployment script now checks remote status explicitly because HDC itself
can exit successfully when its remote shell command fails.

`out/logs/boot-audio-after-verified.txt` records both account and BMS ready,
Launcher and input-method packages installed for user 100, and an ALSA card.
`out/logs/desktop-after-fix.txt` records Launcher process READY and audio_server
PID 4834 still running. Its window dump still shows the lockscreen. These
checks establish startup progress, not successful playback or a visible desktop.

During the later WS73 module loading experiment, HDC and ping stopped responding.
No post-disconnection crash log is available. Keep WS73 out of automatic boot.
Other pending work includes TEE/USB serial service exits, sandbox/cgroup setup,
SELinux labels, GPU/NNRT integration, camera/codec streams and power management.

## Rollback

Restore the three original libraries from the board backup directory with atomic
replacement, then restart accountmgr and audio_server. Preserve account data;
do not erase `/data` to roll back a library. The added empty parent directories
can remain. Module loading was temporary; reboot clears those loaded modules.
The current running board's vendor startup list was not changed by hot deployment.

## Assembled image

`out/images/rdkhm-x5-openharmony-dev.img` passed MBR, SHA256, four filesystem
checks and 146 packaged artifact comparisons. The verifier checks corrected
libraries, storage parent jobs, I2S autoload and WS73 manual-only staging.

SHA256: `79993b1d2c81180420717c968c40be55f9a7bd9d015e7c6791a5db41cfc44562`.
Logs: `out/logs/boot-audio-fix-final-build.log` and
`out/logs/boot-audio-image-verify.log`.
The assembled image has not been flashed or cold-boot tested. Upstream startup
guard warnings remain; a successful build does not clear those findings.
