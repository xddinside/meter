#!/usr/bin/env python3
import json
import os
import subprocess
import re
from pathlib import Path

from .base import Provider, UsageData

class CodexProvider(Provider):
    name = "codex"
    
    def __init__(self, config):
        super().__init__(config)
        self.codex_home = os.environ.get('CODEX_HOME', '~/.codex')
        
    def fetch_usage(self) -> UsageData:
        auth_file = Path(self.codex_home).expanduser() / 'auth.json'
        
        if not auth_file.exists():
            return UsageData(
                provider=self.name,
                error="No auth.json found. Is Codex installed?"
            )
        
        try:
            with open(auth_file) as f:
                auth = json.load(f)
                
            access_token = auth.get('tokens', {}).get('access_token')
            if not access_token:
                return UsageData(provider=self.name, error="No access token in auth.json")
            
            email = auth.get('tokens', {}).get('id_token')
            if email:
                try:
                    import jwt
                    parts = email.split('.')
                    if len(parts) >= 2:
                        payload = json.loads(jwt.decode(parts[1], options={"verify_signature": False}))
                        email = payload.get('email', '')
                except:
                    pass
            
            return self._fetch_via_api(access_token, email)
            
        except json.JSONDecodeError:
            return UsageData(provider=self.name, error="Invalid auth.json")
        except Exception as e:
            return UsageData(provider=self.name, error=str(e))
    
    def _fetch_via_api(self, token: str, email: str = None) -> UsageData:
        try:
            import urllib.request
            
            req = urllib.request.Request(
                'https://chatgpt.com/backend-api/wham/usage',
                headers={
                    'Authorization': f'Bearer {token}',
                }
            )
            
            response = urllib.request.urlopen(req, timeout=10)
            data = json.loads(response.read())
            
            return self._parse_api_response(data, email)
            
        except Exception as e:
            return self._fetch_via_cli_fallback()
    
    def _parse_api_response(self, data: dict, email: str = None) -> UsageData:
        rate_limit = data.get('rate_limit', {})
        
        session_percent = None
        session_remaining = None
        weekly_percent = None
        weekly_remaining = None
        credits = None
        plan = data.get('plan_type', 'unknown')
        
        primary = rate_limit.get('primary_window', {})
        if primary:
            session_percent = primary.get('used_percent', 0)
            reset_after = primary.get('reset_after_seconds')
            if reset_after:
                session_remaining = self._format_seconds(reset_after)
        
        secondary = rate_limit.get('secondary_window', {})
        if secondary:
            weekly_percent = secondary.get('used_percent', 0)
            reset_after = secondary.get('reset_after_seconds')
            if reset_after:
                weekly_remaining = self._format_seconds(reset_after)
        
        return UsageData(
            provider=self.name,
            session_percent=session_percent,
            session_remaining=session_remaining,
            weekly_percent=weekly_percent,
            weekly_remaining=weekly_remaining,
            credits=credits,
            email=email,
            plan=plan
        )
    
    def _format_seconds(self, seconds: int) -> str:
        if seconds >= 86400:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            return f"{days}d {hours}h" if hours > 0 else f"{days}d"
        elif seconds >= 3600:
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            return f"{hours}h {mins}m" if mins > 0 else f"{hours}h"
        elif seconds >= 60:
            return f"{seconds // 60}m"
        else:
            return f"{seconds}s"
    
    def _fetch_via_cli_fallback(self) -> UsageData:
        try:
            result = subprocess.run(
                ['codex', 'exec', '--', 'echo', 'test'],
                capture_output=True,
                text=True,
                timeout=30,
                cwd='/tmp'
            )
            
            return UsageData(
                provider=self.name,
                error="CLI fallback: usage not available via exec"
            )
            
        except FileNotFoundError:
            return UsageData(provider=self.name, error="Codex CLI not found")
        except Exception as e:
            return UsageData(provider=self.name, error=f"CLI error: {e}")
    
    def _format_reset_time(self, reset_time) -> str:
        if not reset_time:
            return None
            
        try:
            from datetime import datetime, timezone
            if isinstance(reset_time, str):
                reset_dt = datetime.fromisoformat(reset_time.replace('Z', '+00:00'))
            else:
                reset_dt = datetime.fromtimestamp(reset_time, tz=timezone.utc)
            
            now = datetime.now(timezone.utc)
            delta = reset_dt - now
            
            hours = delta.total_seconds() / 3600
            if hours > 24:
                return f"{int(hours // 24)}d {int(hours % 24)}h"
            elif hours > 0:
                return f"{int(hours)}h"
            else:
                mins = delta.total_seconds() / 60
                return f"{int(mins)}m"
        except:
            return str(reset_time)
    
    def supports_session(self) -> bool:
        return True
    
    def supports_weekly(self) -> bool:
        return True