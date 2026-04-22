#!/usr/bin/env python3
import argparse
import logging
import os
import sys
import signal
import time
from pathlib import Path
from threading import Lock

from meter.config import Config
from meter.providers import ProviderManager
from meter.ui.tray import SystemTray

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('meter')

class Meter:
    def __init__(self, config_path: str = None, no_tray: bool = False):
        self.config = Config(config_path)
        self._no_tray = no_tray or self.config.no_tray
        self.provider_manager = ProviderManager(self.config)
        self.tray = None
        self.running = False
        
    def start(self):
        logger.info("Starting Meter...")
        
        self.provider_manager.start()
        
        if not self._no_tray:
            self.tray = SystemTray(self.provider_manager, self.config, on_quit_callback=self.stop)
            self.tray.start()
        
        self.running = True
        logger.info("Meter started successfully")
        
    def stop(self):
        logger.info("Stopping Meter...")
        self.running = False
        
        if self.tray:
            self.tray.stop()
        
        self.provider_manager.stop()
        logger.info("Meter stopped")
        
    def wait(self):
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
            
def _setup_autostart():
    """Install systemd user service for autostart on boot."""
    service_dir = Path.home() / '.config' / 'systemd' / 'user'
    service_dir.mkdir(parents=True, exist_ok=True)
    
    service_file = service_dir / 'meter.service'
    
    # Find the meter executable
    meter_path = os.popen('which meter').read().strip()
    if not meter_path:
        # Fallback to python module
        meter_path = f'{sys.executable} -m meter'
    
    service_content = f"""[Unit]
Description=Meter - AI usage tracker for system tray
After=graphical-session.target

[Service]
Type=simple
ExecStart={meter_path}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""
    
    service_file.write_text(service_content)
    
    # Reload and enable
    os.system('systemctl --user daemon-reload')
    os.system('systemctl --user enable meter')
    
    print("Autostart enabled. Meter will start on next login.")
    print("To start now: systemctl --user start meter")

def _remove_autostart():
    """Remove systemd user service and disable autostart."""
    os.system('systemctl --user stop meter 2>/dev/null')
    os.system('systemctl --user disable meter 2>/dev/null')
    
    service_file = Path.home() / '.config' / 'systemd' / 'user' / 'meter.service'
    if service_file.exists():
        service_file.unlink()
    
    # Also remove old desktop autostart if exists
    desktop_file = Path.home() / '.config' / 'autostart' / 'meter.desktop'
    if desktop_file.exists():
        desktop_file.unlink()
    
    os.system('systemctl --user daemon-reload 2>/dev/null')
    print("Autostart disabled. Meter will no longer start on login.")

def main():
    parser = argparse.ArgumentParser(description='Meter - AI usage tracker')
    parser.add_argument('--config', '-c', default=None, help='Config file path')
    parser.add_argument('--no-tray', action='store_true', help='Run without system tray')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--refresh', action='store_true', help='Trigger manual refresh')
    parser.add_argument('--autostart', action='store_true', help='Enable autostart on boot via systemd')
    parser.add_argument('--remove-autostart', action='store_true', help='Disable autostart')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.autostart:
        _setup_autostart()
        sys.exit(0)
    
    if args.remove_autostart:
        _remove_autostart()
        sys.exit(0)
    
    if args.refresh:
        from meter.providers import ProviderManager
        from meter.config import Config
        mgr = ProviderManager(Config(args.config))
        mgr.refresh_all()
        mgr.print_status()
        sys.exit(0)
    
    app = Meter(args.config)
    
    def signal_handler(sig, frame):
        app.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    app.start()
    app.wait()

if __name__ == '__main__':
    main()