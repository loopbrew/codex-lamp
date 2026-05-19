#!/usr/bin/env python3
"""
Small manual tester for Moonside BLE commands.

This script is not used by Codex hooks. It is for verifying that your Mac,
Python environment, bleak install, and lamp can talk before enabling hooks.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("bleak is not installed. Run: python3 -m pip install bleak", file=sys.stderr)
    sys.exit(1)

NUS_TX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"


def color_command(red: int, green: int, blue: int) -> str:
    for value in (red, green, blue):
        if value < 0 or value > 255:
            raise ValueError("color values must be between 0 and 255")
    return f"COLOR{red:03d}{green:03d}{blue:03d}"


def brightness_command(brightness: int) -> str:
    if brightness < 0 or brightness > 120:
        raise ValueError("brightness must be between 0 and 120")
    return f"BRIGH{brightness:03d}"


async def scan(args) -> None:
    devices = await BleakScanner.discover(timeout=args.timeout)
    prefix = args.name_prefix.upper()

    for device in devices:
        name = device.name or ""
        if args.all or name.upper().startswith(prefix):
            print(f"{name or '(unnamed)'}\t{device.address}")


async def find_device(args):
    devices = await BleakScanner.discover(timeout=args.timeout)
    prefix = args.name_prefix.upper()

    for device in devices:
        name = device.name or ""
        address = device.address or ""

        if args.address and address.lower() == args.address.lower():
            return device

        if not args.address and name.upper().startswith(prefix):
            return device

    if args.address:
        raise RuntimeError(f"No BLE device found with address {args.address}")
    raise RuntimeError(f"No BLE device found with name prefix {args.name_prefix}")


async def send_commands(args, commands: list[str]) -> None:
    device = await find_device(args)
    print(f"Connecting to {device.name or '(unnamed)'} ({device.address})")

    async with BleakClient(device, timeout=15.0) as client:
        for command in commands:
            print(f"TX {command}")
            await client.write_gatt_char(
                NUS_TX_UUID,
                command.encode("utf-8"),
                response=True,
            )
            await asyncio.sleep(args.delay)


async def run(args) -> None:
    if args.command == "scan":
        await scan(args)
        return

    if args.command == "on":
        await send_commands(args, ["LEDON"])
        return

    if args.command == "off":
        await send_commands(args, ["LEDOFF"])
        return

    if args.command == "color":
        commands = ["LEDON"]
        if args.brightness is not None:
            commands.append(brightness_command(args.brightness))
        commands.append(color_command(args.red, args.green, args.blue))
        await send_commands(args, commands)
        return

    if args.command == "theme":
        theme = args.name.upper()
        colors = args.colors.rstrip(",")
        await send_commands(args, ["LEDON", f"THEME.{theme}.{colors},"])
        return

    if args.command == "raw":
        await send_commands(args, [args.value])
        return

    raise RuntimeError(f"Unknown command: {args.command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manual Moonside BLE tester")
    parser.add_argument(
        "--name-prefix",
        default=os.environ.get("CODEX_LAMP_NAME_PREFIX", "MOONSIDE"),
        help="BLE device name prefix to scan for",
    )
    parser.add_argument(
        "--address",
        default=os.environ.get("CODEX_LAMP_ADDRESS", ""),
        help="Specific BLE address or macOS UUID",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="scan timeout in seconds")
    parser.add_argument("--delay", type=float, default=0.15, help="delay between writes")

    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="list matching BLE devices")
    scan_parser.add_argument("--all", action="store_true", help="show all BLE devices")

    subparsers.add_parser("on", help="turn lamp on")
    subparsers.add_parser("off", help="turn lamp off")

    color_parser = subparsers.add_parser("color", help="set a solid color")
    color_parser.add_argument("red", type=int)
    color_parser.add_argument("green", type=int)
    color_parser.add_argument("blue", type=int)
    color_parser.add_argument("--brightness", type=int)

    theme_parser = subparsers.add_parser("theme", help="start a Moonside theme")
    theme_parser.add_argument("name", help="theme name, for example BEAT2")
    theme_parser.add_argument(
        "--colors",
        default="255,255,255,0,0,140",
        help="comma-separated RGB values for the theme",
    )

    raw_parser = subparsers.add_parser("raw", help="send one raw command")
    raw_parser.add_argument("value")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        asyncio.run(run(args))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
