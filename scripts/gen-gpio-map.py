#!/usr/bin/env python3
"""Validate the RDK X5 40-pin map and emit the bring-up TSV."""
import argparse
import json
import sys
from pathlib import Path


def validate(data):
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported schema_version")
    chips = data.get("gpiochips") or {}
    power = set(data.get("power_and_ground_pins") or [])
    pins = data.get("pins") or []
    if not pins:
        raise ValueError("No pins in map")
    seen_pin = set()
    seen_gpio = set()
    usable = []
    for pin in pins:
        for key in ("physical_pin", "gpio", "controller", "line", "usable_as_gpio",
                    "mux_owner", "soc_name", "gpiochip"):
            if key not in pin:
                raise ValueError(f"Pin entry missing {key}: {pin}")
        physical = pin["physical_pin"]
        if not isinstance(physical, int) or not 1 <= physical <= 40:
            raise ValueError(f"Invalid physical pin: {physical}")
        if physical in power:
            raise ValueError(f"Physical pin {physical} is listed as power/ground")
        if physical in seen_pin:
            raise ValueError(f"Duplicate physical pin: {physical}")
        seen_pin.add(physical)
        gpio = pin["gpio"]
        if gpio in seen_gpio:
            raise ValueError(f"Duplicate gpio number: {gpio}")
        seen_gpio.add(gpio)
        chip = chips.get(pin["controller"])
        if not chip:
            raise ValueError(f"Unknown controller: {pin['controller']}")
        base = chip["base"]
        if pin["line"] != gpio - base:
            raise ValueError(f"Pin {physical}: line {pin['line']} != gpio {gpio} - base {base}")
        if not 0 <= pin["line"] < chip["ngpio"]:
            raise ValueError(f"Pin {physical}: line {pin['line']} outside {pin['controller']}")
        if pin["gpiochip"] != f"/sys/class/gpio/gpiochip{base}":
            raise ValueError(f"Pin {physical}: unexpected gpiochip path {pin['gpiochip']}")
        if not isinstance(pin["usable_as_gpio"], bool):
            raise ValueError(f"Pin {physical}: usable_as_gpio must be boolean")
        if pin["usable_as_gpio"]:
            usable.append(physical)
    if data.get("usable_as_gpio_now") != usable:
        raise ValueError("usable_as_gpio_now does not match the pin entries")
    return pins, chips


def tsv(pins, chips):
    out = ["#pin\tgpio\tcontroller\tline\tchip_base\tusable\tmux_owner\tsoc_name"]
    for pin in sorted(pins, key=lambda item: item["physical_pin"]):
        owner = pin.get("mux_owner") or "-"
        out.append("\t".join((
            str(pin["physical_pin"]),
            str(pin["gpio"]),
            pin["controller"],
            str(pin["line"]),
            str(chips[pin["controller"]]["base"]),
            "1" if pin["usable_as_gpio"] else "0",
            owner,
            pin["soc_name"],
        )))
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map", type=Path)
    parser.add_argument("tsv", nargs="?", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.map.read_text())
    pins, chips = validate(data)
    usable = [pin["physical_pin"] for pin in pins if pin["usable_as_gpio"]]
    if args.check:
        print(f"PASS: {len(pins)} pins, {len(chips)} controllers, {len(usable)} usable now")
        return 0
    if args.tsv is None:
        raise ValueError("TSV output path is required without --check")
    args.tsv.parent.mkdir(parents=True, exist_ok=True)
    args.tsv.write_text(tsv(pins, chips))
    print(f"Wrote {args.tsv}: {len(pins)} pins, {len(usable)} usable now")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        print(error)
        sys.exit(1)
