#!/usr/bin/env python3
import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Optional

DEFAULT_CONFIG = {
    "providers": {
        "codex": {"enabled": True},
        "opencode": {"enabled": True}
    },
    "refresh_interval": 60,
    "log_dir": "~/.local/share/meter/logs",
    "cache_dir": "~/.cache/meter"
}

@dataclass
class ProviderConfig:
    enabled: bool = True
    cookie: Optional[str] = None

class Config:
    def __init__(self, config_path: str = None):
        self._config = self._load_config(config_path)
        
    def _load_config(self, config_path: str = None) -> Dict:
        if config_path is None:
            config_path = os.environ.get('METER_CONFIG', '~/.config/meter/config.json')
        
        config_file = Path(config_path).expanduser()
        
        if config_file.exists():
            with open(config_file) as f:
                data = json.load(f)
        else:
            data = DEFAULT_CONFIG.copy()
        
        provider_configs = {}
        for name, cfg in data.get('providers', {}).items():
            if isinstance(cfg, dict):
                provider_configs[name] = ProviderConfig(**cfg)
            else:
                provider_configs[name] = ProviderConfig(enabled=bool(cfg))
        
        return {
            'provider_configs': provider_configs,
            'refresh_interval': data.get('refresh_interval', 60),
            'log_dir': Path(data.get('log_dir', '~/.local/share/meter/logs')).expanduser(),
            'cache_dir': Path(data.get('cache_dir', '~/.cache/meter')).expanduser(),
            'no_tray': data.get('no_tray', False)
        }
        
    @property
    def provider_configs(self) -> Dict[str, ProviderConfig]:
        return self._config['provider_configs']
    
    @property
    def refresh_interval(self) -> int:
        return self._config['refresh_interval']
    
    @property
    def cache_dir(self) -> Path:
        return self._config['cache_dir']
    
    @property
    def no_tray(self) -> bool:
        return self._config['no_tray']
    
    def is_enabled(self, provider_name: str) -> bool:
        return self._config['provider_configs'].get(provider_name, ProviderConfig()).enabled
    
    def get_provider_config(self, provider_name: str) -> ProviderConfig:
        return self._config['provider_configs'].get(provider_name, ProviderConfig())
    
    @property
    def providers(self) -> Dict:
        return {name: cfg for name, cfg in self._config['provider_configs'].items()}