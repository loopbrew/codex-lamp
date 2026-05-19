#!/usr/bin/env python3
"""
Codex Lamp BLE daemon.

The hook writes a desired state to /tmp/codex_lamp_state. This daemon keeps a
persistent BLE connection to the Moonside lamp and applies state changes.

States: working, idle, input, off 
"""

from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import signal
import sys
import time

from bleak import BleakClient, BleakScanner

NUS_TX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"

PID_FILE = os.environ.get("CODEX_LAMP_PID_FILE", "/tmp/codex_lamp_daemon.pid")
STATE_FILE = os.environ.get("CODEX_LAMP_STATE_FILE", "/tmp/codex_lamp_state")
LOCK_FILE = os.environ.get("CODEX_LAMP_LOCK_FILE", "/tmp/codex_lamp_daemon.lock")
LOG_FILE = os.environ.get("CODEX_LAMP_LOG_FILE", "/tmp/codex_lamp_daemon.log")

NAME_PREFIX = os.environ.get("CODEX_LAMP_NAME_PREFIX", "MOONSIDE").upper()
DEVICE_ADDRESS = os.environ.get("CODEX_LAMP_ADDRESS", "").strip()
IDLE_TIMEOUT = int(os.environ.get("CODEX_LAMP_IDLE_TIMEOUT", "1800"))


COLOR_IDLE = "COLOR255180050"
WORKING_CMD = "THEME.BEAT2.255,255,255,0,0,140,"
COLOR_INPUT = "THEME.WAVE1.255,100,0,255,26,214,"

VALID_STATES = {"working", "idle", "input", "off"}

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("codex-lamp")


async def discover_lamp(timeout: float = 10.0):
    """Find a lamp by CODEX_LAMP_ADDRESS or CODEX_LAMP_NAME_PREFIX."""
    if DEVICE_ADDRESS:
        log.info("Scanning for device address %s...", DEVICE_ADDRESS)
    else:
        log.info("Scanning for device named %s*...", NAME_PREFIX)

    devices = await BleakScanner.discover(timeout=timeout)
    for device in devices:
        name = device.name or ""
        address = device.address or ""

        if DEVICE_ADDRESS and address.lower() == DEVICE_ADDRESS.lower():
            log.info("Found pinned device: %s (%s)", name, address)
            return device

        if not DEVICE_ADDRESS and name.upper().startswith(NAME_PREFIX):
            log.info("Found lamp: %s (%s)", name, address)
            return device

    if DEVICE_ADDRESS:
        log.error("No BLE device found with address %s", DEVICE_ADDRESS)
    else:
        log.error("No BLE device found with name prefix %s", NAME_PREFIX)
    sys.exit(1)


async def connect_with_retry(device):
    """Connect to the current device, re-scanning once retries are exhausted."""
    delays = [1, 2, 4, 8, 16]

    for delay in delays:
        try:
            client = BleakClient(device, timeout=15.0)
            await client.connect()
            if client.is_connected:
                log.info("Connected to %s (%s)", device.name or "unnamed", device.address)
                return client, device
        except Exception as exc:
            log.warning("Connect failed: %s; retrying in %ss", exc, delay)
            await asyncio.sleep(delay)

    log.warning("Connect retries exhausted; scanning again")
    device = await discover_lamp()
    client = BleakClient(device, timeout=15.0)
    await client.connect()
    log.info("Connected after re-scan to %s (%s)", device.name or "unnamed", device.address)
    return client, device


async def send(client: BleakClient, command: str) -> None:
    log.info("TX %s", command)
    await client.write_gatt_char(NUS_TX_UUID, command.encode("utf-8"), response=True)


def read_state() -> str:
    try:
        with open(STATE_FILE, encoding="utf-8") as state_file:
            return state_file.read().strip()
    except FileNotFoundError:
        return ""
    except OSError as exc:
        log.warning("Could not read state file: %s", exc)
        return ""


def write_pid() -> None:
    with open(PID_FILE, "w", encoding="utf-8") as pid_file:
        pid_file.write(str(os.getpid()))


def cleanup() -> None:
    try:
        if os.path.exists(PID_FILE):
            with open(PID_FILE, encoding="utf-8") as pid_file:
                pid = pid_file.read().strip()
            if pid == str(os.getpid()):
                os.unlink(PID_FILE)
    except OSError:
        pass


async def apply_state(client: BleakClient, state: str) -> bool:
    """Apply a lamp state. Return False when the daemon should exit."""
    if state == "working":
        await send(client, "LEDON")
        await asyncio.sleep(0.1)
        await send(client, WORKING_CMD)
        return True

    if state == "idle":
        await send(client, "LEDON")
        await asyncio.sleep(0.1)
        await send(client, COLOR_IDLE)
        return True

    if state == "input":
        await send(client, "LEDON")
        await asyncio.sleep(0.1)
        await send(client, COLOR_INPUT)
        return True

    if state == "off":
        await send(client, "LEDOFF")
        return False

    return True


async def main() -> None:
    lock_file = open(LOCK_FILE, "w", encoding="utf-8")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log.info("Another daemon is already running")
        return

    write_pid()

    shutdown = asyncio.Event()

    def request_shutdown(*_):
        shutdown.set()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    device = await discover_lamp()
    client, device = await connect_with_retry(device)

    current_state = ""
    idle_since: float | None = None

    try:
        while not shutdown.is_set():
            desired_state = read_state()

            if desired_state and desired_state not in VALID_STATES:
                log.warning("Ignoring unknown state: %s", desired_state)
                desired_state = current_state

            if desired_state != current_state:
                log.info("State change: %s -> %s", current_state or "none", desired_state)
                current_state = desired_state
                idle_since = time.monotonic() if current_state == "idle" else None

                try:
                    if not client.is_connected:
                        client, device = await connect_with_retry(device)

                    keep_running = await apply_state(client, current_state)
                    if not keep_running:
                        break
                except Exception as exc:
                    log.error("BLE send failed: %s", exc)
                    try:
                        client, device = await connect_with_retry(device)
                    except Exception as reconnect_exc:
                        log.error("Reconnect failed: %s", reconnect_exc)

            if current_state == "idle" and idle_since is not None:
                if time.monotonic() - idle_since >= IDLE_TIMEOUT:
                    log.info("Idle timeout reached; turning lamp off")
                    try:
                        if client.is_connected:
                            await send(client, "LEDOFF")
                    except Exception as exc:
                        log.warning("Idle shutdown send failed: %s", exc)
                    break

            await asyncio.sleep(0.2)

    finally:
        try:
            if client.is_connected:
                await client.disconnect()
        except Exception as exc:
            log.warning("Disconnect failed: %s", exc)
        cleanup()
        log.info("Daemon exited")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
