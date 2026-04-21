#!/usr/bin/env python3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger('codexbar.providers')

@dataclass
class UsageData:
    provider: str
    session_percent: Optional[float] = None
    session_remaining: Optional[str] = None
    weekly_percent: Optional[float] = None
    weekly_remaining: Optional[str] = None
    credits: Optional[float] = None
    credits_unlimited: bool = False
    email: Optional[str] = None
    plan: Optional[str] = None
    error: Optional[str] = None
    last_updated: datetime = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()
    
    @property
    def is_error(self) -> bool:
        return self.error is not None
    
    @property
    def summary(self) -> str:
        if self.error:
            return f"Error: {self.error}"
        
        parts = []
        if self.session_percent is not None:
            parts.append(f"Session: {self.session_percent:.0f}%")
        if self.weekly_percent is not None:
            parts.append(f"Weekly: {self.weekly_percent:.0f}%")
        if self.credits is not None:
            if self.credits_unlimited:
                parts.append("Credits: ∞")
            else:
                parts.append(f"Credits: ${self.credits:.2f}")
        
        return " / ".join(parts) if parts else "No data"

class Provider(ABC):
    name: str = "provider"
    
    def __init__(self, config):
        self.config = config
        self._usage: Optional[UsageData] = None
        
    @abstractmethod
    def fetch_usage(self) -> UsageData:
        """Fetch usage data from the provider. Override in subclasses."""
        pass
    
    @property
    def usage(self) -> Optional[UsageData]:
        return self._usage
    
    def refresh(self) -> UsageData:
        try:
            self._usage = self.fetch_usage()
            logger.debug(f"{self.name}: {self._usage.summary}")
        except Exception as e:
            logger.error(f"{self.name}: Failed to fetch usage: {e}")
            self._usage = UsageData(provider=self.name, error=str(e))
        return self._usage
    
    def is_enabled(self) -> bool:
        return self.config.is_enabled(self.name)
    
    def supports_session(self) -> bool:
        return False
    
    def supports_weekly(self) -> bool:
        return False
    
    def supports_credits(self) -> bool:
        return False