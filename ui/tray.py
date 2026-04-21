#!/usr/bin/env python3
import threading
import logging
from datetime import datetime
from typing import Optional, List

import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger('codexbar.ui')

class SystemTray:
    def __init__(self, provider_manager, config):
        self.provider_manager = provider_manager
        self.config = config
        self.icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None
        
    def _create_icon_image(self, status_text: str = None) -> Image:
        width, height = 64, 64
        image = Image.new('RGB', (width, height), color='#1a1a2e')
        draw = ImageDraw.Draw(image)
        
        bar_width = 16
        bar_height = 24
        bar_gap = 4
        
        x1 = (width - bar_width * 2 - bar_gap) // 2
        y1 = (height - bar_height - bar_gap - 8) // 2
        
        draw.rectangle([x1, y1, x1 + bar_width, y1 + bar_height], fill='#4ade80')
        
        y2 = y1 + bar_height + bar_gap
        draw.rectangle([x1, y2, x1 + bar_width, y2 + 8], fill='#22c55e')
        
        if status_text:
            try:
                draw.text((width // 2, height - 8), '●', fill='#ef4444', anchor='mm')
            except:
                pass
        
        return image
    
    def _get_menu_items(self) -> List[pystray.MenuItem]:
        items = []
        
        items.append(pystray.MenuItem('─ CodexBar ─', None, enabled=False))
        items.append(pystray.Menu.SEPARATOR)
        
        usage_data = self.provider_manager.get_all_usage()
        
        if not usage_data:
            items.append(pystray.MenuItem('No providers', None, enabled=False))
        else:
            provider_names = list(usage_data.keys())
            for i, name in enumerate(provider_names):
                if i > 0:
                    items.append(pystray.Menu.SEPARATOR)
                for item in self._format_usage_items(name, usage_data[name]):
                    items.append(item)
        
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem('Refresh', self._on_refresh))
        items.append(pystray.MenuItem('Quit', self._on_quit))
        
        return items
    
    def _format_usage_items(self, name: str, usage) -> List[pystray.MenuItem]:
        items = []
        
        if not usage:
            items.append(pystray.MenuItem(f"{name.capitalize()}: Loading...", None, enabled=False))
            return items
        
        if usage.is_error:
            items.append(pystray.MenuItem(f"{name.capitalize()}: ⚠ {usage.error}", None, enabled=False))
            return items
        
        items.append(pystray.MenuItem(f"{name.capitalize()}:", None, enabled=False))
        
        if usage.session_percent is not None:
            session_str = f"Session: {usage.session_percent:.0f}%"
            if usage.session_remaining:
                session_str += f" ({usage.session_remaining})"
            items.append(pystray.MenuItem(session_str, None, enabled=False))
        
        if usage.weekly_percent is not None:
            weekly_str = f"Weekly: {usage.weekly_percent:.0f}%"
            if usage.weekly_remaining:
                weekly_str += f" ({usage.weekly_remaining})"
            items.append(pystray.MenuItem(weekly_str, None, enabled=False))
        
        if usage.credits is not None:
            items.append(pystray.MenuItem(f"Credits: ${usage.credits:.2f}", None, enabled=False))
        
        if len(items) == 1:
            items.append(pystray.MenuItem("No data", None, enabled=False))
        
        return items
    
    def _build_menu(self):
        return pystray.Menu(*self._get_menu_items())
    
    def _update_icon(self):
        if not self.icon:
            return
            
        usage_data = self.provider_manager.get_all_usage()
        has_errors = any(u and u.is_error for u in usage_data.values())
        
        image = self._create_icon_image('error' if has_errors else '')
        self.icon.icon = image
        
        menu = self._build_menu()
        self.icon.menu = menu
        
        title_parts = []
        for name, usage in usage_data.items():
            if usage and not usage.is_error:
                if usage.session_percent is not None and usage.weekly_percent is not None:
                    title_parts.append(f"{name[:1].upper()}:S{usage.session_percent:.0f}% W{usage.weekly_percent:.0f}%")
                elif usage.session_percent is not None:
                    title_parts.append(f"{name[:1].upper()}:{usage.session_percent:.0f}%")
                elif usage.credits is not None:
                    title_parts.append(f"{name[:1].upper()}:${usage.credits:.2f}")
        
        self.icon.title = ' | '.join(title_parts) if title_parts else 'CodexBar'
    
    def _on_refresh(self):
        logger.info("Manual refresh triggered")
        self.provider_manager.refresh_all()
        self._update_icon()
    
    def _on_quit(self):
        logger.info("Quit requested from tray")
        self.provider_manager._running = False
        if self.icon:
            self.icon.stop()
    
    def start(self):
        def run_icon():
            menu = self._build_menu()
            image = self._create_icon_image()
            
            self.icon = pystray.Icon(
                'codexbar',
                image,
                'CodexBar',
                menu
            )
            
            self.icon.run()
        
        self._thread = threading.Thread(target=run_icon, daemon=True)
        self._thread.start()
        
        def update_loop():
            while True:
                try:
                    self._update_icon()
                except Exception as e:
                    logger.error(f"Icon update error: {e}")
                import time
                time.sleep(10)
        
        self._update_thread = threading.Thread(target=update_loop, daemon=True)
        self._update_thread.start()
        
        logger.info("System tray started")
    
    def stop(self):
        if self.icon:
            self.icon.stop()
            self.icon = None
        logger.info("System tray stopped")