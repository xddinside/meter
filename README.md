# Meter

A minimalist Linux system tray app that tracks AI usage limits — inspired by [CodexBar](https://github.com/steipete/codexbar) by [@steipete](https://github.com/steipete).

## What it does

Meter sits in your system tray and shows real-time usage stats for:

- **OpenAI Codex** — session & weekly limits (from `~/.codex/auth.json`)
- **OpenCode Go** — rolling usage & weekly limits (opt-in, via browser cookies or CLI fallback)

No browser windows. No dashboards. Just glance at your tray.

## Screenshot

```
─ Meter ─
Codex:
  Session: 14% (4h 21m)
  Weekly: 13% (6d 8h)
──────────
Opencode:
  Credits: $15.71
──────────
Refresh
Quit
```

## Requirements

- Python 3.10+
- GTK / AppIndicator support (for system tray)
- Linux with a systray (works on Hyprland, i3, Sway, GNOME, KDE, etc.)

## Installation

### Option 1: AUR (Arch Linux)

```bash
yay -S meter-tray
# or
paru -S meter-tray
# or manually
git clone https://aur.archlinux.org/meter-tray.git
cd meter-tray
makepkg -si
```

### Option 2: pip (recommended)

```bash
git clone https://github.com/xddinside/meter.git
cd meter
pip install -e .
```

Then run:
```bash
meter
```

### Option 3: Manual

```bash
git clone https://github.com/xddinside/meter.git
cd meter
pip install pystray pillow
python -m meter
```

### Autostart

Meter uses a **systemd user service** for autostart (cleaner than desktop files):

```bash
# Enable autostart on boot
meter --autostart

# Start now (without enabling autostart)
systemctl --user start meter

# Check status
systemctl --user status meter

# View logs
journalctl --user -u meter -f

# Disable autostart
meter --remove-autostart
```

## Configuration

Config lives at `~/.config/meter/config.json`:

```json
{
  "providers": {
    "codex": {"enabled": true},
    "opencode": {
      "enabled": false,
      "cookie": null
    }
  },
  "refresh_interval": 60
}
```

### Setting up OpenCode Go

OpenCode is optional and starts disabled. Enable it when you want Meter to show
OpenCode usage too:

```bash
meter --enable-opencode
systemctl --user restart meter
```

You can turn it off again anytime:

```bash
meter --disable-opencode
systemctl --user restart meter
```

The OpenCode provider needs your browser cookies to fetch usage. Here's how:

1. Go to [opencode.ai](https://opencode.ai) and log in
2. Open DevTools (F12) → **Network** tab
3. Refresh the page
4. Click any request → **Headers** → copy the full `Cookie:` value
5. Paste it into `~/.config/meter/config.json`:

```json
{
  "providers": {
    "opencode": {
      "enabled": true,
      "cookie": "your-opencode-cookie"
    }
  }
}
```

## CLI

```bash
meter --help

Options:
  -c, --config PATH    Config file path
  --no-tray            Run without system tray (print once and exit)
  --debug              Enable debug logging
  --refresh            Trigger a manual refresh and print status
  --autostart          Enable autostart on boot via systemd
  --remove-autostart   Disable autostart
  --enable-opencode    Enable the OpenCode provider in the config
  --disable-opencode   Disable the OpenCode provider in the config
```

## Uninstall

```bash
# If installed via pip
pip uninstall meter-tray

# If installed via AUR
yay -R meter-tray

# Remove user data (optional)
rm -rf ~/.config/meter ~/.cache/meter ~/.local/share/meter
```

## Troubleshooting

**"OpenCode CLI not found"**
- Make sure `opencode` is in your PATH. Meter searches common locations including `~/.nvm/versions/node/*/bin/`.

**OpenCode is not showing**
- Enable it with `meter --enable-opencode`, then restart Meter.
- Add a cookie in `~/.config/meter/config.json` if browser cookie detection does not find your login.

**No tray icon showing**
- Install a system tray implementation like `waybar`, `polybar`, or `stalonetray`
- On GNOME: install the [AppIndicator extension](https://extensions.gnome.org/extension/615/appindicator-support/)

**Codex shows "No data"**
- Make sure you've run `codex` at least once so `~/.codex/auth.json` exists

## Credits

Inspired by [CodexBar](https://github.com/steipete/codexbar) by Peter Steinberger ([@steipete](https://github.com/steipete)).

## License

MIT
