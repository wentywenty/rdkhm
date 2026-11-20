#!/usr/bin/env python3
"""Continuously capture the RDK X5 serial console and write an audit log.

The board console is exposed through ser2net, for example:
    socket://127.0.0.1:22298

By default the complete raw stream is written to out/board-logs/serial-*.log
and only lines matching the important-pattern set are printed. Use --all to
print every line, or --filter to replace the pattern set.
"""
import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import serial
except ImportError:
    print("pyserial is required: python3 -m pip install pyserial", file=sys.stderr)
    raise

DEFAULT_PATTERNS = [
    r"\bpanic\b", r"\bOops\b", r"Internal error", r"\bwatchdog\b",
    r"\bwdt\b", r"pretimeout", r"PM: suspend", r"PM: resume",
    r"BootROM", r"Starting kernel", r"Run /rdkhm/init",
    r"boot_id", r"\bMAC:\b", r"devicec MAC", r"eth0",
    r"hdcd", r"HDC", r"displayId", r"InputWindowsManager",
    r"teecd", r"power_interface", r"hdf_device_host",
    r"usb_serial_host",
]


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="socket://127.0.0.1:22298")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--log-dir", default="out/board-logs")
    parser.add_argument("--name", default="serial")
    parser.add_argument("--filter", action="append", default=None,
                        help="regex to print; may be repeated")
    parser.add_argument("--all", action="store_true", help="print every line")
    parser.add_argument("--duration", type=float, default=0,
                        help="seconds to run; 0 means forever")
    parser.add_argument("--reconnect-delay", type=float, default=2)
    return parser.parse_args()


def main():
    args = parse_args()
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = log_dir / f"{args.name}-{stamp}.log"
    patterns = args.filter if args.filter else DEFAULT_PATTERNS
    show = re.compile("|".join(patterns), re.IGNORECASE)
    deadline = time.time() + args.duration if args.duration > 0 else None
    started = time.time()
    print(f"serial log: {log_path.resolve()}", flush=True)

    while deadline is None or time.time() < deadline:
        try:
            port = serial.serial_for_url(args.url, baudrate=args.baud,
                                         timeout=1)
        except Exception as exc:
            print(f"serial connect failed: {exc}", file=sys.stderr, flush=True)
            time.sleep(args.reconnect_delay)
            continue
        print(f"serial connected: {args.url}", flush=True)
        pending = b""
        try:
            with log_path.open("ab", buffering=0) as log:
                while deadline is None or time.time() < deadline:
                    data = port.read(8192)
                    if not data:
                        continue
                    log.write(data)
                    pending += data
                    while b"\n" in pending:
                        raw, pending = pending.split(b"\n", 1)
                        line = (raw + b"\n").decode("utf-8", "replace")
                        if args.all or show.search(line):
                            print(line, end="", flush=True)
        except KeyboardInterrupt:
            print("\nserial monitor stopped", flush=True)
            break
        except Exception as exc:
            print(f"serial read failed: {exc}", file=sys.stderr, flush=True)
        finally:
            try:
                port.close()
            except Exception:
                pass
        if deadline is None or time.time() < deadline:
            time.sleep(args.reconnect_delay)

    print(f"captured {time.time() - started:.1f}s -> {log_path.resolve()}",
          flush=True)


if __name__ == "__main__":
    main()
