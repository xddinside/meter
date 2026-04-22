#!/usr/bin/env python3
import logging
import threading
import time
import json
from pathlib import Path
from typing import Dict, List, Optional

from .base import Provider, UsageData
from .codex import CodexProvider
from .opencode import OpenCodeProvider

logger = logging.getLogger('meter.providers')

class ProviderManager:
    PROVIDER_CLASSES = {
        'codex': CodexProvider,
        'opencode': OpenCodeProvider,
    }
    
    def __init__(self, config):
        self.config = config
        self.providers: Dict[str, Provider] = {}
        self._polling_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        
        self._init_providers()
        
    def _init_providers(self):
        for name, cls in self.PROVIDER_CLASSES.items():
            if self.config.is_enabled(name):
                try:
                    self.providers[name] = cls(self.config)
                    logger.info(f"Initialized provider: {name}")
                except Exception as e:
                    logger.error(f"Failed to initialize {name}: {e}")
            else:
                logger.info(f"Provider disabled: {name}")
                    
    def start(self):
        self._running = True
        self._polling_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._polling_thread.start()
        
        for provider in self.providers.values():
            provider.refresh()
            
    def stop(self):
        self._running = False
        if self._polling_thread:
            self._polling_thread.join(timeout=2)
            
    def _polling_loop(self):
        while self._running:
            self.refresh_all()
            time.sleep(self.config.refresh_interval)
            
    def refresh_all(self):
        with self._lock:
            for name, provider in self.providers.items():
                try:
                    provider.refresh()
                except Exception as e:
                    logger.error(f"Error refreshing {name}: {e}")
                    
    def get_all_usage(self) -> Dict[str, UsageData]:
        with self._lock:
            return {name: p.usage for name, p in self.providers.items() if p.usage}
    
    def get_status_json(self) -> str:
        data = {}
        with self._lock:
            for name, provider in self.providers.items():
                if provider.usage:
                    u = provider.usage
                    data[name] = {
                        'session_percent': u.session_percent,
                        'session_remaining': u.session_remaining,
                        'weekly_percent': u.weekly_percent,
                        'weekly_remaining': u.weekly_remaining,
                        'credits': u.credits,
                        'credits_unlimited': u.credits_unlimited,
                        'email': u.email,
                        'plan': u.plan,
                        'error': u.error,
                        'last_updated': u.last_updated.isoformat() if u.last_updated else None
                    }
        return json.dumps(data, indent=2)
    
    def print_status(self):
        print("\n=== Meter Status ===")
        for name, provider in self.providers.items():
            if provider.usage:
                print(f"\n{name.upper()}:")
                print(f"  {provider.usage.summary}")
            else:
                print(f"\n{name.upper()}: No data")
                
    def get_menu_items(self) -> List[Dict]:
        items = []
        for name, provider in self.providers.items():
            if not provider.usage:
                continue
                
            u = provider.usage
            item = {
                'name': name,
                'label': name.capitalize(),
                'status': u.summary if not u.is_error else f"⚠️ {u.error}",
                'is_error': u.is_error
            }
            items.append(item)
        return items