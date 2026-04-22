#!/usr/bin/env python3
import math
import threading
import logging
from importlib import resources
from typing import Optional, List, Dict

import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger('meter.ui')

# Progress bar characters — geometric, clean
_BAR_FULL = '◼'
_BAR_EMPTY = '◻'
_BAR_WIDTH = 5

# Brand colors (RGB tuples)
_BRAND_COLORS = {
    'codex': (16, 163, 127),      # OpenAI green #10a37f
    'opencode': (99, 102, 241),   # Indigo #6366f1
}

# Usage status colors
_USAGE_COLORS = {
    'low': (16, 185, 129),      # Emerald
    'med': (245, 158, 11),      # Amber
    'high': (239, 68, 68),      # Red
}


def _mini_bar(percent: float, width: int = _BAR_WIDTH) -> str:
    """Generate a compact progress bar."""
    filled = int((percent / 100) * width)
    return _BAR_FULL * filled + _BAR_EMPTY * (width - filled)


def _compact_time(remaining: str) -> str:
    """Compress time string for menu width."""
    return remaining.replace(' ', '') if remaining else ''


def _usage_level(percent: float) -> str:
    """Return usage level string."""
    if percent >= 90:
        return 'high'
    elif percent >= 70:
        return 'med'
    return 'low'


def _load_logo(name: str, size: int = 16) -> Optional[Image.Image]:
    """Load provider logo as a PIL Image."""
    try:
        logo_path = resources.files('meter').joinpath(f'assets/logos/{name}.png')
        with resources.as_file(logo_path) as path:
            with Image.open(path) as img:
                return img.convert('RGBA').resize((size, size), Image.Resampling.LANCZOS)
    except Exception:
        return None


def _create_text_badge(text: str, color: tuple, size: int = 16) -> Image.Image:
    """Create a text badge icon with colored background."""
    image = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw circle background
    draw.ellipse([0, 0, size - 1, size - 1], fill=(*color, 255))
    
    # Draw text centered
    bbox = draw.textbbox((0, 0), text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2
    y = (size - text_h) // 2 - 1
    
    draw.text((x, y), text, fill=(255, 255, 255, 255))
    return image


def _paste_image(base: Image.Image, overlay: Image.Image, x: int, y: int):
    """Paste overlay onto base with alpha blending."""
    if overlay.mode == 'RGBA':
        base.paste(overlay, (x, y), overlay)
    else:
        base.paste(overlay, (x, y))


class SystemTray:
    def __init__(self, provider_manager, config, on_quit_callback=None):
        self.provider_manager = provider_manager
        self.config = config
        self.on_quit_callback = on_quit_callback
        self.icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None
        self._update_thread: Optional[threading.Thread] = None
        self._base_icon_image: Optional[Image.Image] = None
        self._logo_cache: Dict[str, Image.Image] = {}
        self._stopping = False

    def _get_logo(self, name: str, size: int = 16) -> Optional[Image.Image]:
        """Get cached logo image for a provider."""
        cache_key = f"{name}_{size}"
        if cache_key not in self._logo_cache:
            logo = _load_logo(name, size)
            if logo is None:
                # Fallback to text badge
                color = _BRAND_COLORS.get(name, (99, 102, 241))
                logo = _create_text_badge(name[:1].upper(), color, size)
            self._logo_cache[cache_key] = logo
        return self._logo_cache[cache_key]

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

    def _create_dynamic_icon(self, usage_data: dict) -> Image.Image:
        """Create a dynamic icon showing provider status."""
        size = 64
        image = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Background circle
        draw.ellipse([4, 4, size - 4, size - 4], fill=(30, 30, 30, 240), outline=(60, 60, 60, 200), width=2)
        
        providers = list(usage_data.keys())
        
        if not providers:
            # Default "M" icon
            draw.text((26, 20), "M", fill=(255, 255, 255, 200))
            return image
        
        # Draw provider logos arranged in a grid
        if len(providers) == 1:
            # Single provider - logo centered with ring
            name = providers[0]
            usage = usage_data[name]
            logo = self._get_logo(name, 24)
            
            if logo:
                _paste_image(image, logo, 20, 12)
            
            # Status ring around the edge
            if usage and not usage.is_error:
                if usage.session_percent is not None:
                    color = _USAGE_COLORS[_usage_level(usage.session_percent)]
                    draw.arc([8, 8, size - 8, size - 8], start=0, end=360, 
                            fill=(*color, 200), width=3)
        else:
            # Multiple providers - arrange in a grid
            positions = [
                (12, 12),  # Top-left
                (36, 12),  # Top-right
                (12, 36),  # Bottom-left
                (36, 36),  # Bottom-right
            ]
            
            for i, (name, usage) in enumerate(usage_data.items()):
                if i >= 4:
                    break
                x, y = positions[i]
                logo = self._get_logo(name, 16)
                
                if logo:
                    _paste_image(image, logo, x, y)
                
                # Status dot
                if usage and not usage.is_error and usage.session_percent is not None:
                    color = _USAGE_COLORS[_usage_level(usage.session_percent)]
                    dot_x, dot_y = x + 18, y + 18
                    draw.ellipse([dot_x, dot_y, dot_x + 8, dot_y + 8], 
                                fill=(*color, 255), outline=(255, 255, 255, 200), width=1)
        
        # Error indicator
        has_errors = any(u and u.is_error for u in usage_data.values())
        if has_errors:
            draw.ellipse([size - 20, 0, size, 20], fill=(239, 68, 68, 230))
            draw.text((size - 14, 3), "!", fill=(255, 255, 255, 255))
        
        return image

    def _create_icon_image(self, usage_data: dict = None) -> Image:
        if usage_data is not None:
            return self._create_dynamic_icon(usage_data)
        return self._load_base_icon() or self._create_dynamic_icon({})

    def _get_menu_items(self) -> List[pystray.MenuItem]:
        items = []
        usage_data = self.provider_manager.get_all_usage()

        if not usage_data:
            items.append(pystray.MenuItem('No providers configured', None, enabled=False))
        else:
            for name, usage in usage_data.items():
                items.extend(self._format_provider_items(name, usage))

        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem('Refresh', self._on_refresh))
        items.append(pystray.MenuItem('Quit', self._on_quit))

        return items

    def _format_provider_items(self, name: str, usage) -> List[pystray.MenuItem]:
        items = []

        if not usage:
            items.append(pystray.MenuItem(
                f"{name.capitalize()}  ·  loading...", None, enabled=False))
            return items

        if usage.is_error:
            items.append(pystray.MenuItem(
                f"{name.capitalize()}  ·  {usage.error}", None, enabled=False))
            return items

        # Provider header with stats
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
            label = f"  Session   {bar}  {usage.session_percent:.0f}%"
            if usage.session_remaining:
                label += f"  ·  {_compact_time(usage.session_remaining)}"
            items.append(pystray.MenuItem(label, None, enabled=False))

        # Weekly with progress bar
        if usage.weekly_percent is not None:
            bar = _mini_bar(usage.weekly_percent)
            label = f"  Weekly    {bar}  {usage.weekly_percent:.0f}%"
            if usage.weekly_remaining:
                label += f"  ·  {_compact_time(usage.weekly_remaining)}"
            items.append(pystray.MenuItem(label, None, enabled=False))

        # Credits (no bar, clean currency display)
        if usage.credits is not None:
            label = f"  Credits   ${usage.credits:.2f}"
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
            
            # Create dynamic icon with provider logos
            image = self._create_icon_image(usage_data)
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
            # Start with empty usage data
            image = self._create_icon_image({})

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
