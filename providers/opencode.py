#!/usr/bin/env python3
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Optional

import urllib.request

from .base import Provider, UsageData


class OpenCodeProvider(Provider):
    name = "opencode"

    WORKSPACES_SERVER_ID = "def39973159c7f0483d8793a822b8dbb10d067e12c65455fcb4608459ba0234f"

    def __init__(self, config):
        super().__init__(config)
        self.cookie_sources = [
            self._get_chrome_cookies,
            self._get_firefox_cookies,
        ]

    def fetch_usage(self) -> UsageData:
        cookie_header = self._get_config_cookie()

        if not cookie_header:
            cookie_header = self._get_browser_cookies()

        if cookie_header:
            result = self._fetch_via_api(cookie_header)
            if not result.is_error:
                return result

        return self._fetch_via_cli_fallback()

    def _get_config_cookie(self) -> Optional[str]:
        provider_config = self.config.get_provider_config(self.name)
        cookie = provider_config.cookie
        if cookie and isinstance(cookie, str) and len(cookie) > 10:
            return cookie
        return None

    def _fetch_via_api(self, cookie_header: str) -> UsageData:
        try:
            workspace_id = self._get_workspace_id(cookie_header)
            if not workspace_id:
                return UsageData(provider=self.name, error="Could not find workspace ID")

            usage_text = self._get_usage_page(workspace_id, cookie_header)
            return self._parse_usage(usage_text)

        except Exception as e:
            return UsageData(provider=self.name, error=str(e))

    def _get_workspace_id(self, cookie_header: str) -> Optional[str]:
        try:
            url = f"https://opencode.ai/_server?id={self.WORKSPACES_SERVER_ID}"

            req = urllib.request.Request(url, headers={
                'Cookie': cookie_header,
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
                'Accept': 'text/javascript, application/json',
                'X-Server-Id': self.WORKSPACES_SERVER_ID,
                'Origin': 'https://opencode.ai',
                'Referer': 'https://opencode.ai',
            })

            response = urllib.request.urlopen(req, timeout=10)
            text = response.read().decode('utf-8')

            if self._looks_signed_out(text):
                return None

            ids = re.findall(r'id\s*:\s*"([^"]+)"', text)
            for id in ids:
                if id.startswith('wrk_'):
                    return id

            ids = self._parse_workspace_ids_from_json(text)
            if ids:
                return ids[0]

            fallback_url = f"https://opencode.ai/_server?id={self.WORKSPACES_SERVER_ID}&args=%5B%5D"
            req = urllib.request.Request(fallback_url, headers={
                'Cookie': cookie_header,
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
                'Accept': 'text/javascript, application/json',
                'X-Server-Id': self.WORKSPACES_SERVER_ID,
                'Origin': 'https://opencode.ai',
                'Referer': 'https://opencode.ai',
                'Content-Type': 'application/json',
            })

            response = urllib.request.urlopen(req, timeout=10)
            text = response.read().decode('utf-8')

            if self._looks_signed_out(text):
                return None

            ids = re.findall(r'id\s*:\s*"([^"]+)"', text)
            for id in ids:
                if id.startswith('wrk_'):
                    return id

            ids = self._parse_workspace_ids_from_json(text)
            if ids:
                return ids[0]

            return None

        except Exception:
            return None

    def _parse_workspace_ids_from_json(self, text: str) -> list:
        try:
            obj = json.loads(text)
            results = []
            self._collect_workspace_ids(obj, results)
            return results
        except:
            return []

    def _collect_workspace_ids(self, obj, results):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == 'id' and isinstance(value, str) and value.startswith('wrk_'):
                    results.append(value)
                else:
                    self._collect_workspace_ids(value, results)
        elif isinstance(obj, list):
            for item in obj:
                self._collect_workspace_ids(item, results)

    def _looks_signed_out(self, text: str) -> bool:
        lower = text.lower()
        return ('login' in lower or 'sign in' in lower or
                'auth/authorize' in lower or
                'not associated with an account' in lower or
                'actor of type "public"' in lower)

    def _get_usage_page(self, workspace_id: str, cookie_header: str) -> str:
        url = f"https://opencode.ai/workspace/{workspace_id}/go"

        req = urllib.request.Request(url, headers={
            'Cookie': cookie_header,
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })

        response = urllib.request.urlopen(req, timeout=10)
        return response.read().decode('utf-8')

    def _parse_usage(self, text: str) -> UsageData:
        rolling_percent = None
        rolling_reset = None
        weekly_percent = None
        weekly_reset = None

        rolling_match = re.search(r'rollingUsage[^}]*?usagePercent\s*:\s*([0-9]+(?:\.[0-9]+)?)', text)
        if rolling_match:
            rolling_percent = float(rolling_match.group(1))

        rolling_reset_match = re.search(r'rollingUsage[^}]*?resetInSec\s*:\s*([0-9]+)', text)
        if rolling_reset_match:
            rolling_reset = int(rolling_reset_match.group(1))

        weekly_match = re.search(r'weeklyUsage[^}]*?usagePercent\s*:\s*([0-9]+(?:\.[0-9]+)?)', text)
        if weekly_match:
            weekly_percent = float(weekly_match.group(1))

        weekly_reset_match = re.search(r'weeklyUsage[^}]*?resetInSec\s*:\s*([0-9]+)', text)
        if weekly_reset_match:
            weekly_reset = int(weekly_reset_match.group(1))

        if rolling_percent is None and weekly_percent is None:
            snapshot = self._parse_usage_json(text)
            if snapshot:
                return snapshot

        if rolling_percent is None and weekly_percent is None:
            return UsageData(provider=self.name, error="Could not parse usage data")

        return UsageData(
            provider=self.name,
            session_percent=rolling_percent,
            session_remaining=self._format_seconds(rolling_reset) if rolling_reset else None,
            weekly_percent=weekly_percent,
            weekly_remaining=self._format_seconds(weekly_reset) if weekly_reset else None
        )

    def _parse_usage_json(self, text: str) -> Optional[UsageData]:
        try:
            obj = json.loads(text)

            keys_to_try = ['data', 'result', 'usage', 'billing', 'payload']
            for key in keys_to_try:
                if key in obj and isinstance(obj[key], dict):
                    usage = self._extract_usage_from_dict(obj[key])
                    if usage:
                        return usage

            usage = self._extract_usage_from_dict(obj)
            if usage:
                return usage

        except:
            pass
        return None

    def _extract_usage_from_dict(self, d: dict) -> Optional[UsageData]:
        rolling_keys = ['rollingUsage', 'rolling', 'rolling_usage', 'rollingWindow', 'rolling_window']
        weekly_keys = ['weeklyUsage', 'weekly', 'weekly_usage', 'weeklyWindow', 'weekly_window']

        rolling = None
        for key in rolling_keys:
            if key in d and isinstance(d[key], dict):
                rolling = d[key]
                break

        weekly = None
        for key in weekly_keys:
            if key in d and isinstance(d[key], dict):
                weekly = d[key]
                break

        if not rolling or not weekly:
            return None

        rolling_percent = self._extract_percent(rolling)
        rolling_reset = self._extract_reset_seconds(rolling)
        weekly_percent = self._extract_percent(weekly)
        weekly_reset = self._extract_reset_seconds(weekly)

        if rolling_percent is None and weekly_percent is None:
            return None

        return UsageData(
            provider=self.name,
            session_percent=rolling_percent,
            session_remaining=self._format_seconds(rolling_reset) if rolling_reset else None,
            weekly_percent=weekly_percent,
            weekly_remaining=self._format_seconds(weekly_reset) if weekly_reset else None
        )

    def _extract_percent(self, d: dict) -> Optional[float]:
        percent_keys = ['usagePercent', 'usedPercent', 'percentUsed', 'percent', 'usage_percent']
        for key in percent_keys:
            if key in d:
                val = d[key]
                if isinstance(val, (int, float)):
                    percent = float(val)
                    if percent <= 1.0:
                        percent *= 100
                    return max(0, min(100, percent))
                elif isinstance(val, str):
                    try:
                        return float(val)
                    except:
                        pass
        return None

    def _extract_reset_seconds(self, d: dict) -> Optional[int]:
        reset_keys = ['resetInSec', 'resetInSeconds', 'resetSeconds', 'reset_sec']
        for key in reset_keys:
            if key in d:
                val = d[key]
                if isinstance(val, (int, float)):
                    return int(val)
                elif isinstance(val, str):
                    try:
                        return int(float(val))
                    except:
                        pass
        return None

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
        import subprocess
        import shutil

        # Add common paths where opencode might be installed
        custom_paths = [
            os.path.expanduser('~/.nvm/versions/node/v24.13.1/bin'),
            os.path.expanduser('~/.nvm/versions/node/current/bin'),
            os.path.expanduser('~/.local/bin'),
            os.path.expanduser('~/.npm-global/bin'),
            '/usr/local/bin',
        ]

        env = {**os.environ, 'FORCE_COLOR': '0'}
        current_path = env.get('PATH', '')
        new_paths = [p for p in custom_paths if os.path.isdir(p) and p not in current_path]
        if new_paths:
            env['PATH'] = ':'.join(new_paths) + ':' + current_path

        # Find opencode binary
        opencode_bin = shutil.which('opencode', path=env.get('PATH', os.environ.get('PATH', '')))
        if not opencode_bin:
            return UsageData(provider=self.name, error="OpenCode CLI not found")

        try:
            result = subprocess.run(
                [opencode_bin, 'stats'],
                capture_output=True,
                text=True,
                timeout=15,
                env=env
            )

            if result.returncode != 0:
                stderr = result.stderr.strip()[:100]
                return UsageData(
                    provider=self.name,
                    error=f"OpenCode stats failed: {stderr}" if stderr else "OpenCode stats failed"
                )

            return self._parse_stats_output(result.stdout)

        except subprocess.TimeoutExpired:
            return UsageData(provider=self.name, error="OpenCode stats timeout")
        except Exception as e:
            return UsageData(provider=self.name, error=f"Stats failed: {e}")

    def _parse_stats_output(self, output: str) -> UsageData:
        cost_match = re.search(r'Total Cost\s+\$([0-9.]+)', output)
        if cost_match:
            return UsageData(
                provider=self.name,
                credits=float(cost_match.group(1))
            )
        return UsageData(provider=self.name, error="Could not parse stats output")

    def _get_browser_cookies(self) -> Optional[str]:
        for source in self.cookie_sources:
            cookies = source()
            if cookies:
                return cookies
        return None

    def _get_chrome_cookies(self) -> Optional[str]:
        cookie_paths = [
            Path(os.path.expanduser('~/.config/google-chrome/Default/Cookies')),
            Path(os.path.expanduser('~/.config/chromium/Default/Cookies')),
        ]

        for cookie_path in cookie_paths:
            if not cookie_path.exists():
                continue

            try:
                conn = sqlite3.connect(str(cookie_path))
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT name, value FROM cookies WHERE host_key LIKE '%opencode.ai%'"
                )

                cookies = []
                for name, value in cursor.fetchall():
                    cookies.append(f"{name}={value}")

                conn.close()

                if cookies:
                    return "; ".join(cookies)
            except Exception:
                continue

        return None

    def _get_firefox_cookies(self) -> Optional[str]:
        firefox_dirs = [
            Path(os.path.expanduser('~/.mozilla/firefox')),
            Path(os.path.expanduser('~/.librewolf')),
        ]

        for base_dir in firefox_dirs:
            if not base_dir.exists():
                continue

            for profile_dir in base_dir.glob('*'):
                if not profile_dir.is_dir():
                    continue

                cookie_path = profile_dir / 'cookies.sqlite'
                if not cookie_path.exists():
                    continue

                try:
                    conn = sqlite3.connect(str(cookie_path))
                    cursor = conn.cursor()

                    cursor.execute(
                        "SELECT name, value FROM moz_cookies WHERE host LIKE '%opencode.ai%'"
                    )

                    cookies = []
                    for name, value in cursor.fetchall():
                        cookies.append(f"{name}={value}")

                    conn.close()

                    if cookies:
                        return "; ".join(cookies)
                except Exception:
                    continue

        return None

    def supports_session(self) -> bool:
        return True

    def supports_weekly(self) -> bool:
        return True

    def supports_credits(self) -> bool:
        return True
