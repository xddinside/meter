#!/usr/bin/env python3
import argparse
import logging
import os
import sys
import signal
import time
from pathlib import Path
from threading import Lock

from config import Config
from providers import ProviderManager
from ui.tray import SystemTray

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('codexbar')

class CodexBar:
    def __init__(self, config_path: str = None, no_tray: bool = False):
        self.config = Config(config_path)
        self._no_tray = no_tray or self.config.no_tray
        self.provider_manager = ProviderManager(self.config)
        self.tray = None
        self.running = False
        
    def start(self):
        logger.info("Starting CodexBar...")
        
        self.provider_manager.start()
        
        if not self._no_tray:
            self.tray = SystemTray(self.provider_manager, self.config)
            self.tray.start()
        
        self.running = True
        logger.info("CodexBar started successfully")
        
    def stop(self):
        logger.info("Stopping CodexBar...")
        self.running = False
        
        if self.tray:
            self.tray.stop()
        
        self.provider_manager.stop()
        logger.info("CodexBar stopped")
        
    def wait(self):
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
            
def main():
    parser = argparse.ArgumentParser(description='CodexBar - AI usage tracker')
    parser.add_argument('--config', '-c', default=None, help='Config file path')
    parser.add_argument('--no-tray', action='store_true', help='Run without system tray')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--refresh', action='store_true', help='Trigger manual refresh')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.refresh:
        from providers import ProviderManager
        from config import Config
        mgr = ProviderManager(Config(args.config))
        mgr.refresh_all()
        mgr.print_status()
        sys.exit(0)
    
    app = CodexBar(args.config)
    
    def signal_handler(sig, frame):
        app.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    app.start()
    app.wait()

if __name__ == '__main__':
    main()