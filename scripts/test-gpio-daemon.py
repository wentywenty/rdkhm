#!/usr/bin/env python3
"""Host-side smoke test for the GPIO socket service protocol."""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def wait_for(path, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            return True
        time.sleep(0.02)
    return False


def exchange(client, request):
    client.sendall(request.encode() + b"\n")
    data = b""
    while not data.endswith(b".\n"):
        chunk = client.recv(4096)
        if not chunk:
            break
        data += chunk
    return data.decode()


def main():
    with tempfile.TemporaryDirectory(prefix="rdkhm-gpio-") as directory:
        temp = Path(directory)
        daemon = temp / "gpio-daemon"
        tool = temp / "gpio"
        sock = temp / "gpio.sock"
        compile_result = subprocess.run(
            ["gcc", "-O2", "-Wall", "-Wextra", "-Werror",
             str(ROOT / "bringup/gpio/rdkhm-gpio-daemon.c"), "-o", str(daemon)],
            capture_output=True, text=True)
        assert compile_result.returncode == 0, compile_result.stderr
        tool.write_text("#!/bin/sh\nprintf 'ARGS'\nfor arg in \"$@\"; do printf ' <%s>' \"$arg\"; done\nprintf '\\n'\n")
        tool.chmod(0o755)
        env = os.environ.copy()
        env["RDKHM_GPIO_SOCKET"] = str(sock)
        env["RDKHM_GPIO_TOOL"] = str(tool)
        # The test process is not root; opt the invoking UID into the Unix
        # socket peer check and explicitly enable the debug TCP listener.
        env["RDKHM_GPIO_ALLOWED_UID"] = str(os.getuid())
        env["RDKHM_GPIO_TCP_ENABLE"] = "1"
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        env["RDKHM_GPIO_TCP_PORT"] = str(port)
        process = subprocess.Popen([str(daemon), "-f"], env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            if not wait_for(sock):
                process.terminate()
                _, error = process.communicate(timeout=5)
                raise AssertionError(error.decode())
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(str(sock))
                reply = exchange(client, "list")
                assert reply.startswith("OK\n") and "list" in reply, reply
                reply = exchange(client, "show 7")
                assert reply.startswith("OK\n") and "<show> <7>" in reply, reply
                reply = exchange(client, "show 41")
                assert reply.startswith("ERR 2\n"), reply
                reply = exchange(client, "bogus")
                assert reply.startswith("ERR 2\n"), reply
                reply = exchange(client, "ping")
                assert reply == "OK\nPONG\n.\n", reply
                reply = exchange(client, "quit")
                assert reply == "", reply
            with socket.create_connection(("127.0.0.1", port), timeout=2) as tcp:
                reply = exchange(tcp, "ping")
                assert reply == "OK\nPONG\n.\n", reply
        finally:
            process.terminate()
            process.wait(timeout=5)
    print("GPIO daemon socket smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
