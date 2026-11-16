#!/usr/bin/env python3
"""Exercise capture, serial forwarding, rotation and bounded exit off-board."""
from pathlib import Path
import socket
import subprocess
import tempfile

workspace = Path(__file__).resolve().parents[1]
source = (workspace / "bringup/capture-hilog.sh").read_text()
with tempfile.TemporaryDirectory(prefix="rdkhm-hilog-") as directory:
    root = Path(directory)
    logs = root / "logs"
    logs.mkdir()
    (logs / "hilog-current.txt").write_text("previous boot\n")
    console = root / "console"
    endpoint = root / "hilogOutput"
    wrapper = root / "bb"
    wrapper.write_text('''#!/bin/sh
case "$1" in
    sleep) /bin/sleep 0.2 ;;
    sync) exit 0 ;;
    *) exec "$@" ;;
esac
''')
    wrapper.chmod(0o755)
    client = root / "hilog"
    client.write_text('''#!/bin/sh
echo 'RSRenderService init failed.'
echo 'Get HdiDevice failed'
exec /bin/sleep 20
''')
    client.chmod(0o755)
    script = root / "capture.sh"
    script.write_text(source.replace("bb=/rdkhm/busybox", f"bb={wrapper}")
                      .replace("/data/rdkhm-logs", str(logs))
                      # A real console is not truncated when opened; emulate that.
                      .replace(">/dev/console", f">>{console}")
                      .replace("/dev/unix/socket/hilogOutput", str(endpoint))
                      .replace("/system/bin/hilog", str(client)))
    # Real Unix socket: exercise the same -S gate as the board script.
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(str(endpoint))
        subprocess.run(["/bin/sh", str(script)], check=True, timeout=10)
    assert "Get HdiDevice failed" in console.read_text()
    assert "RSRenderService init failed." in (logs / "hilog-current.txt").read_text()
    assert (logs / "hilog-previous.txt").read_text() == "previous boot\n"
    print("PASS: socket gate, capture, serial forwarding, rotation and bounded exit")
