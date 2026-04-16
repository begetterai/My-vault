#!/usr/bin/env python3
"""
Poster API client для Ромашки
Токен: Личная интеграция
"""

import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta

TOKEN = "398711:8746917c4a23ea897774040e039dfb76"
BASE_URL = "https://joinposter.com/api"

def api_get(method, params=None):
    """Выполнить GET запрос к Poster API"""
    if params is None:
        params = {}
    params["token"] = TOKEN
    url = f"{BASE_URL}/{method}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data
    except Exception as e:
        return {"error": str(e)}

# Тест 1: Информация об аккаунте
print("=== Информация об аккаунте ===")
info = api_get("settings.getBusinessSettings")
print(json.dumps(info, ensure_ascii=False, indent=2))

