#!/usr/bin/env python3
"""Generate the ArkTS pin table used by the PinTool HAP."""
import json
import sys
from pathlib import Path


def main():
    source = Path(sys.argv[1])
    target = Path(sys.argv[2])
    data = json.loads(source.read_text())
    lines = [
        'export class PinRecord {',
        '  physical_pin: number;',
        '  gpio: number;',
        '  controller: string;',
        '  line: number;',
        '  usable_as_gpio: boolean;',
        '  mux_owner: string;',
        '  soc_name: string;',
        '  note: string;',
        '',
        '  constructor(pin: number, gpio: number, controller: string, line: number, usable: boolean, owner: string, soc: string, note: string) {',
        '    this.physical_pin = pin;',
        '    this.gpio = gpio;',
        '    this.controller = controller;',
        '    this.line = line;',
        '    this.usable_as_gpio = usable;',
        '    this.mux_owner = owner;',
        '    this.soc_name = soc;',
        '    this.note = note;',
        '  }',
        '}',
        '',
        'export const PIN_DATA: PinRecord[] = [',
    ]
    for pin in sorted(data["pins"], key=lambda item: item["physical_pin"]):
        owner = pin.get("mux_owner") or ""
        values = [
            str(pin["physical_pin"]), str(pin["gpio"]),
            json.dumps(pin["controller"]), str(pin["line"]),
            "true" if pin["usable_as_gpio"] else "false",
            json.dumps(owner), json.dumps(pin["soc_name"]), json.dumps(pin["note"]),
        ]
        lines.append("  new PinRecord(" + ", ".join(values) + "),")
    lines.append("];")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n")
    print(f"Wrote {target}: {len(data['pins'])} pins")


if __name__ == "__main__":
    sys.exit(main())
