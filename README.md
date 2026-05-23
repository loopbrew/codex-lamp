# Codex Lamp

A cool physical status light for Codex.

This project connects Codex lifecycle hooks to a [Moonside](https://moonside.design/) lamp, so the
lamp changes color or animation as Codex starts working, asks for approval, or
finishes a turn.

It is intentionally small:

- Codex hooks stay fast and quiet.
- A shell hook writes the desired lamp state.
- One background Python daemon owns the Bluetooth connection.
- The daemon sends simple Moonside BLE commands.

```text
Codex hook event
  -> codex_lamp_hook.sh
       writes /tmp/codex_lamp_state
       starts the daemon if needed
  -> codex_lamp_daemon.py
       keeps one BLE connection alive
       watches for state changes
       sends commands to the lamp
```

## What It Looks Like

| Codex moment | Lamp state | Default lamp effect |
| --- | --- | --- |
| Codex starts, resumes, or clears a session | `idle` | Warm amber solid light |
| You submit a prompt | `working` | Animated blue/white working theme |
| Codex runs a supported tool | `working` | Animated blue/white working theme |
| Codex asks for approval | `input` | Purple solid light |
| Codex finishes a turn | `idle` | Warm amber solid light |
| Manual off or idle timeout | `off` | LED off |

The default effects are defined in `codex_lamp_daemon.py`:

```python
COLOR_IDLE = "COLOR255180050"
WORKING_CMD = "THEME.BEAT2.255,255,255,0,0,140,"
COLOR_INPUT = "THEME.WAVE1.255,100,0,255,26,214,"
```

You can change these commands to any Moonside command your lamp accepts. Moonside API Documentation: https://developer.moonside.design/

## Project Files

| File | Purpose |
| --- | --- |
| `hooks.json` | Example Codex hook configuration. Copy or merge this into `~/.codex/hooks.json`. |
| `codex_lamp_hook.sh` | Fast Codex hook entrypoint. It writes the state file and starts the daemon. |
| `codex_lamp_daemon.py` | Background BLE daemon. It watches the state file and controls the lamp. |
| `codex_lamp_test.py` | Manual BLE tester for scanning, colors, themes, and raw commands. |
| `README.md` | Setup, usage, and troubleshooting guide. |

## Requirements

- macOS
- Python 3.10 or newer
- A Moonside lamp that accepts Nordic UART Service commands
- Bluetooth enabled
- The Python package `bleak`
- Codex with local hooks support

Install `bleak` into the Python environment that Codex can reach:

```sh
python3 -m pip install bleak
```

The hook auto-detects Python in this order:

1. `CODEX_LAMP_PYTHON`, if set
2. `python3`
3. `/opt/homebrew/bin/python3`
4. `$CONDA_PREFIX/bin/python3`, if Conda is active

## Quick Start

### 1. Test the lamp directly

From this project folder:

```sh
python3 codex_lamp_test.py scan
```

You should see something like:

```text
MOONSIDE-O101    A2F26067-F4DB-DAD8-FB91-70D6A2E9CCC0
```

Then test a few direct commands:

```sh
python3 codex_lamp_test.py off
python3 codex_lamp_test.py color 255 180 50
python3 codex_lamp_test.py color 255 0 0
python3 codex_lamp_test.py theme BEAT2 --colors 255,255,255,0,0,140
```

If these work, Bluetooth, Python, `bleak`, and the lamp are all talking.

### 2. Test the hook and daemon locally

Still from this project folder:

```sh
bash codex_lamp_hook.sh working
bash codex_lamp_hook.sh input
bash codex_lamp_hook.sh idle
bash codex_lamp_hook.sh off
```

The lamp should react to each state.

Check the daemon log if something does not respond:

```sh
tail -n 80 /tmp/codex_lamp_daemon.log
```

### 3. Install the scripts for Codex

Copy the scripts into a stable location under your Codex home:

```sh
mkdir -p ~/.codex/codex-lamp
cp codex_lamp_hook.sh codex_lamp_daemon.py codex_lamp_test.py ~/.codex/codex-lamp/
chmod +x ~/.codex/codex-lamp/codex_lamp_hook.sh
chmod +x ~/.codex/codex-lamp/codex_lamp_daemon.py
chmod +x ~/.codex/codex-lamp/codex_lamp_test.py
```

Copy or merge the example hook config:

```sh
cp hooks.json ~/.codex/hooks.json
```

If you already have `~/.codex/hooks.json`, merge the `hooks` entries instead of
overwriting your existing file.

### 4. Make sure Codex hooks are enabled

Current Codex builds enable hooks by default. To be explicit, you can add this
to `~/.codex/config.toml`:

```toml
[features]
hooks = true
```

Older Codex builds used the deprecated alias:

```toml
[features]
codex_hooks = true
```

Prefer `hooks = true` for current Codex versions.

After changing hook configuration, restart Codex.

### 5. Review and trust the hook

Codex may ask you to review non-managed command hooks before they run. In the
Codex CLI, use:

```text
/hooks
```

Review the command paths and trust the hooks if they match your local install.

## Hook Mapping

The included `hooks.json` maps Codex events to lamp states:

| Codex hook | When it fires | Lamp state |
| --- | --- | --- |
| `SessionStart` | Codex starts, resumes, or clears a session | `idle` |
| `UserPromptSubmit` | You send a prompt to Codex | `working` |
| `PreToolUse` | Codex is about to run a supported tool | `working` |
| `PostToolUse` | Codex finished a supported tool call | `working` |
| `PermissionRequest` | Codex is about to ask for approval | `input` |
| `Stop` | Codex finished the turn | `idle` |

The `PermissionRequest` hook is intentionally narrow. It only fires when Codex
is about to ask for approval, such as a sandbox escalation or managed network
approval. It does not fire every time Codex is waiting for your next message.

## Manual Commands

You can drive the lamp without Codex:

```sh
bash ~/.codex/codex-lamp/codex_lamp_hook.sh working
bash ~/.codex/codex-lamp/codex_lamp_hook.sh input
bash ~/.codex/codex-lamp/codex_lamp_hook.sh idle
bash ~/.codex/codex-lamp/codex_lamp_hook.sh off
```

These are useful for testing, filming demos, or resetting the lamp.

## Demoing PermissionRequest

`PermissionRequest` is not common during normal use because Codex only asks for
approval when it crosses a permission boundary.

For a predictable demo, start Codex in a stricter mode and ask it to do a
harmless write:

```sh
codex --sandbox read-only --ask-for-approval on-request
```

Then prompt Codex:

```text
Create a harmless file named permission_demo.txt in this folder with the text
"Codex lamp demo". Since this session is read-only, request approval before
making the edit.
```

Expected lamp flow:

```text
prompt submitted -> working
approval needed  -> input
approved action  -> working
turn complete    -> idle
```

## Configuration

The scripts can be configured with environment variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| `CODEX_LAMP_PYTHON` | auto-detect | Python executable that has `bleak` installed. |
| `CODEX_LAMP_DAEMON` | script next to the hook | Override daemon script path. |
| `CODEX_LAMP_NAME_PREFIX` | `MOONSIDE` | BLE device name prefix to scan for. |
| `CODEX_LAMP_ADDRESS` | unset | Pin one lamp by BLE address or macOS UUID. |
| `CODEX_LAMP_IDLE_TIMEOUT` | `1800` | Seconds before idle daemon turns the lamp off and exits. |
| `CODEX_LAMP_STATE_FILE` | `/tmp/codex_lamp_state` | Shared desired-state file. |
| `CODEX_LAMP_PID_FILE` | `/tmp/codex_lamp_daemon.pid` | Daemon PID file. |
| `CODEX_LAMP_LOCK_FILE` | `/tmp/codex_lamp_daemon.lock` | Lock file that prevents duplicate daemons. |
| `CODEX_LAMP_LOG_FILE` | `/tmp/codex_lamp_daemon.log` | Hook and daemon log file. |

### Pin a specific lamp

If you have multiple BLE devices nearby, pin the lamp address:

```sh
export CODEX_LAMP_ADDRESS="A2F26067-F4DB-DAD8-FB91-70D6A2E9CCC0"
bash ~/.codex/codex-lamp/codex_lamp_hook.sh idle
```

For permanent use, set the environment variable wherever your Codex shell
environment is configured.

### Shorten the idle auto-off time

By default, the daemon turns the lamp off after 30 minutes of idle time. For a
shorter timeout:

```sh
export CODEX_LAMP_IDLE_TIMEOUT=120
```

That means:

```text
Codex finishes -> idle light
2 minutes pass -> lamp off
```

## Customizing Effects

Edit these constants in `codex_lamp_daemon.py`:

```python
WORKING_CMD = "THEME.BEAT2.255,255,255,0,0,140,"
COLOR_IDLE = "COLOR255180050"
COLOR_INPUT = "COLOR200000255"
```

For example, to make approval requests use an animated wave instead of a solid
purple color:

```python
COLOR_INPUT = "THEME.WAVE1.255,100,0,255,26,214,"
```

After changing the installed daemon file, restart the daemon:

```sh
bash ~/.codex/codex-lamp/codex_lamp_hook.sh off
bash ~/.codex/codex-lamp/codex_lamp_hook.sh idle
```

## Moonside Commands Used

This project sends ASCII commands over the Nordic UART Service write
characteristic:

```text
6e400002-b5a3-f393-e0a9-e50e24dcca9e
```

Examples:

| Action | Command |
| --- | --- |
| LED on | `LEDON` |
| LED off | `LEDOFF` |
| Solid color | `COLOR255180050` |
| Brightness | `BRIGH060` |
| Theme | `THEME.BEAT2.255,255,255,0,0,140,` |

Use the tester to try raw commands:

```sh
python3 codex_lamp_test.py raw "LEDOFF"
python3 codex_lamp_test.py raw "THEME.WAVE1.255,100,0,255,26,214,"
```

## Multiple Sessions

This version is a single-lamp, shared-state design.

All Codex sessions write to the same state file:

```text
/tmp/codex_lamp_state
```

That means the latest hook event wins.

Example:

```text
Session A -> working
lamp      -> working

Session B -> idle
lamp      -> idle
```

Even if Session A is still working, Session B's later `idle` event can overwrite
the lamp state.

For one main Codex session, this is simple and works well. For heavy multi-session
use, the next design would parse Codex's hook JSON from `stdin`, track each
`session_id`, and compute a global state:

```text
if any session needs approval -> input
else if any session is working -> working
else -> idle
```

For multiple lamps, a future router could assign each active `session_id` to a
specific lamp.

## Session Close Behavior

Codex currently exposes `Stop` as a turn-level hook, not a true
session/window-close hook.

So this project can reliably detect:

```text
turn finished -> idle
```

It cannot detect perfectly:

```text
terminal window closed
desktop app window closed
session abandoned
```

The practical workaround is the idle timeout. If Codex stops producing hook
events, the daemon eventually turns the lamp off.

## Troubleshooting

### The lamp does not show up

Run:

```sh
python3 codex_lamp_test.py scan --all
```

If you see the lamp with a different name, use:

```sh
python3 codex_lamp_test.py --name-prefix YOUR_PREFIX scan
```

If scanning is flaky, pin the address:

```sh
CODEX_LAMP_ADDRESS="YOUR-LAMP-ADDRESS" python3 codex_lamp_test.py off
```

### `bleak` is installed, but the hook cannot find it

Find the Python that has `bleak`:

```sh
python3 -c "import sys, bleak; print(sys.executable)"
```

Then point the hook at it:

```sh
export CODEX_LAMP_PYTHON="/path/to/python3"
```

### The direct tester works, but Codex does not trigger the lamp

Check these in order:

1. `~/.codex/hooks.json` contains the hook commands.
2. The hook paths point to the installed script.
3. The script is executable.
4. Codex has reviewed/trusted the hook with `/hooks`.
5. Hooks are not disabled in `~/.codex/config.toml`.
6. The daemon log has useful clues:

```sh
tail -n 120 /tmp/codex_lamp_daemon.log
```

You can also manually run the exact installed command:

```sh
bash "$HOME/.codex/codex-lamp/codex_lamp_hook.sh" working
```

### The daemon seems stuck

Turn the lamp off through the hook first:

```sh
bash ~/.codex/codex-lamp/codex_lamp_hook.sh off
```

If needed, stop the daemon manually:

```sh
kill "$(cat /tmp/codex_lamp_daemon.pid)"
rm -f /tmp/codex_lamp_daemon.pid /tmp/codex_lamp_daemon.lock
```

Then start it again:

```sh
bash ~/.codex/codex-lamp/codex_lamp_hook.sh idle
```

### The Desktop app behaves differently from the CLI

Start by testing with the Codex CLI, because hook behavior is easiest to inspect
there with `/hooks` and the local logs.

If your Desktop build does not appear to trigger hooks, keep the hook project as
is and consider a separate Desktop watcher that observes Codex logs or app
activity and calls the same `codex_lamp_hook.sh` states. That keeps the BLE code
centralized and avoids duplicating lamp control logic.

## Safety Notes

- These scripts control your own Bluetooth lamp at your own risk.
- Codex hooks run local commands, so read the scripts before trusting them.
- The hook is intentionally quiet and exits `0` so lamp failures do not break
  Codex turns.
- The daemon writes temporary state, PID, lock, and log files under `/tmp` by
  default.

## Credits

This project was inspired by [bobek-balinek/claude-lamp](https://github.com/bobek-balinek/claude-lamp), a Claude hook project for controlling a Moonside lamp from Claude activity.

## Useful Links

- Codex hooks documentation: https://developers.openai.com/codex/hooks
- Codex configuration basics: https://developers.openai.com/codex/config-basic
- Bleak documentation: https://bleak.readthedocs.io/
