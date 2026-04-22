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
            
def main():
    parser = argparse.ArgumentParser(description='Meter - AI usage tracker')
    parser.add_argument('--config', '-c', default=None, help='Config file path')
    parser.add_argument('--no-tray', action='store_true', help='Run without system tray')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--refresh', action='store_true', help='Trigger manual refresh')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
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