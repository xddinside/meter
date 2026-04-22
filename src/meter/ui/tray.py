#!/usr/bin/env python3
import math
import threading
import logging
from importlib import resources
from typing import Optional, List

import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger('meter.ui')

# Unicode blocks for mini progress bars
_BAR_FULL = '█'
_BAR_EMPTY = '░'
_BAR_BLOCKS = ['░', '▒', '▓', '█']


def _mini_bar(percent: float, width: int = 6) -> str:
    """Generate a compact Unicode progress bar."""
    filled = int((percent / 100) * width)
    remainder = (percent / 100) * width - filled
    
    bar = _BAR_FULL * filled
    if filled < width and remainder > 0:
        idx = min(int(remainder * 4), 3)
        bar += _BAR_BLOCKS[idx]
        bar += _BAR_EMPTY * (width - filled - 1)
    else:
        bar += _BAR_EMPTY * (width - filled)
    
    return bar


def _status_emoji(percent: float) -> str:
    """Return a status indicator based on usage percentage."""
    if percent >= 90:
        return '🔴'
    elif percent >= 70:
        return '🟡'
    elif percent >= 40:
        return '🟢'
    return '⚪'


class SystemTray:
    def __init__(self, provider_manager, config, on_quit_callback=None):
        self.provider_manager = provider_manager
        self.config = config
        self.on_quit_callback = on_quit_callback
        self.icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None
        self._update_thread: Optional[threading.Thread] = None
        self._base_icon_image: Optional[Image.Image] = None
        self._stopping = False

    def _load_base_icon(self) -> Optional[Image.Image]:
        if self._base_icon_image is not None:
            return self._base_icon_image.copy()

        try:
            resource = resources.files('meter').joinpath('assets/tray-icon.png')
            with resources.as_file(resource) as icon_path:
                with Image.open(icon_path) as icon_image:
                    self._base_icon_image = icon_image.convert('RGBA').resize((64, 64), Image.Resampling.LANCZOS)
        except Exception as exc:
            logger.warning(f"Falling back to generated icon: {exc}")
            self._base_icon_image = None

        return self._base_icon_image.copy() if self._base_icon_image else None

    def _create_fallback_icon_image(self) -> Image.Image:
        width, height = 64, 64
        image = Image.new('RGBA', (width, height), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Draw a gauge-like icon
        cx, cy = width // 2, height // 2 + 4
        radius = 24
        
        # Background arc
        draw.arc([cx - radius, cy - radius, cx + radius, cy + radius], 
                 start=180, end=360, fill=(80, 80, 80, 180), width=6)
        
        # Active arc (partial)
        draw.arc([cx - radius, cy - radius, cx + radius, cy + radius], 
                 start=180, end=270, fill=(76, 175, 80, 255), width=6)
        
        # Center dot
        draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(255, 255, 255, 200))
        
        # Tick marks
        for angle in [180, 225, 270, 315, 360]:
            rad = math.radians(angle)
            x1 = cx + (radius - 8) * math.cos(rad)
            y1 = cy + (radius - 8) * math.sin(rad)
            x2 = cx + (radius - 4) * math.cos(rad)
            y2 = cy + (radius - 4) * math.sin(rad)
            draw.line([x1, y1, x2, y2], fill=(255, 255, 255, 150), width=2)

        return image

    def _create_icon_image(self, status_text: str = None) -> Image:
        image = self._load_base_icon() or self._create_fallback_icon_image()
        
        if status_text:
            draw = ImageDraw.Draw(image)
            # Error badge
            draw.ellipse((44, 44, 62, 62), fill=(239, 68, 68, 230))
            draw.ellipse((46, 46, 60, 60), fill=(239, 68, 68, 255))

        return image

    def _get_menu_items(self) -> List[pystray.MenuItem]:
        items = []
        usage_data = self.provider_manager.get_all_usage()

        if not usage_data:
            items.append(pystray.MenuItem('No providers configured', None, enabled=False))
        else:
            for name, usage in usage_data.items():
                items.extend(self._format_provider_items(name, usage))

        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem('🔄 Refresh', self._on_refresh))
        items.append(pystray.MenuItem('✕ Quit', self._on_quit))

        return items

    def _format_provider_items(self, name: str, usage) -> List[pystray.MenuItem]:
        items = []

        if not usage:
            items.append(pystray.MenuItem(
                f"{name.capitalize()}  ⏳ Loading...", None, enabled=False))
            return items

        if usage.is_error:
            items.append(pystray.MenuItem(
                f"⚠ {name.capitalize()}: {usage.error}", None, enabled=False))
            return items

        # Provider header with key stat
        header_parts = [name.capitalize()]
        if usage.session_percent is not None:
            header_parts.append(f"S:{usage.session_percent:.0f}%")
        if usage.weekly_percent is not None:
            header_parts.append(f"W:{usage.weekly_percent:.0f}%")
        if usage.credits is not None:
            header_parts.append(f"${usage.credits:.2f}")
        
        items.append(pystray.MenuItem(
            '  '.join(header_parts), None, enabled=False))

        # Session with progress bar
        if usage.session_percent is not None:
            bar = _mini_bar(usage.session_percent)
            emoji = _status_emoji(usage.session_percent)
            label = f"  {emoji} Session  {bar}  {usage.session_percent:.0f}%"
            if usage.session_remaining:
                label += f"  ·  {usage.session_remaining}"
            items.append(pystray.MenuItem(label, None, enabled=False))

        # Weekly with progress bar
        if usage.weekly_percent is not None:
            bar = _mini_bar(usage.weekly_percent)
            emoji = _status_emoji(usage.weekly_percent)
            label = f"  {emoji} Weekly  {bar}  {usage.weekly_percent:.0f}%"
            if usage.weekly_remaining:
                label += f"  ·  {usage.weekly_remaining}"
            items.append(pystray.MenuItem(label, None, enabled=False))

        # Credits (no bar, just formatted)
        if usage.credits is not None:
            label = f"  💰 Credits  ${usage.credits:.2f}"
            items.append(pystray.MenuItem(label, None, enabled=False))

        if len(items) == 1:
            items.append(pystray.MenuItem("  No data available", None, enabled=False))

        return items

    def _build_menu(self):
        return pystray.Menu(*self._get_menu_items())

    def _update_icon(self):
        if self._stopping or not self.icon:
            return

        try:
            usage_data = self.provider_manager.get_all_usage()
            has_errors = any(u and u.is_error for u in usage_data.values())

            image = self._create_icon_image('error' if has_errors else '')
            self.icon.icon = image

            menu = self._build_menu()
            self.icon.menu = menu

            # Compact tooltip
            title_parts = []
            for name, usage in usage_data.items():
                if usage and not usage.is_error:
                    if usage.session_percent is not None:
                        title_parts.append(f"{name[:2].upper()}: {usage.session_percent:.0f}%")
                    elif usage.credits is not None:
                        title_parts.append(f"{name[:2].upper()}: ${usage.credits:.2f}")

            self.icon.title = '  '.join(title_parts) if title_parts else 'Meter'
        except Exception as e:
            if not self._stopping:
                logger.error(f"Icon update error: {e}")

    def _on_refresh(self):
        logger.info("Manual refresh triggered")
        self.provider_manager.refresh_all()
        self._update_icon()

    def _on_quit(self):
        logger.info("Quit requested from tray")
        self._stopping = True
        self.provider_manager._running = False

        if self.on_quit_callback:
            try:
                self.on_quit_callback()
            except Exception as e:
                logger.error(f"Quit callback error: {e}")

        if self.icon:
            try:
                self.icon.stop()
            except Exception as e:
                logger.error(f"Icon stop error: {e}")
            self.icon = None

    def start(self):
        self._stopping = False

        def run_icon():
            menu = self._build_menu()
            image = self._create_icon_image()

            self.icon = pystray.Icon(
                'meter',
                image,
                'Meter',
                menu
            )

            self.icon.run()

        self._thread = threading.Thread(target=run_icon, daemon=True)
        self._thread.start()

        def update_loop():
            while not self._stopping:
                try:
                    self._update_icon()
                except Exception as e:
                    if not self._stopping:
                        logger.error(f"Icon update error: {e}")
                import time
                time.sleep(10)

        self._update_thread = threading.Thread(target=update_loop, daemon=True)
        self._update_thread.start()

        logger.info("System tray started")

    def stop(self):
        self._stopping = True
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
        logger.info("System tray stopped")
