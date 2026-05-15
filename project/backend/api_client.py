"""
DeepSeek API 客户端
负责调用 DeepSeek 官方 API 获取余额和 Token 用量信息
"""

import requests
import time
from typing import Optional, Dict, Any

DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class DeepSeekAPIClient:
    """DeepSeek API 封装客户端"""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })
        self._last_balance: Optional[Dict[str, Any]] = None
        self._last_fetch_time: float = 0
        self._cache_ttl: int = 30

    def set_api_key(self, api_key: str):
        self.api_key = api_key
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
        })
        self._last_balance = None
        self._last_fetch_time = 0

    def get_balance(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        now = time.time()
        if not force_refresh and self._last_balance and (now - self._last_fetch_time) < self._cache_ttl:
            return self._last_balance

        try:
            resp = self.session.get(
                f"{DEEPSEEK_BASE_URL}/user/balance",
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                infos = data.get("balance_infos", [])
                first = infos[0] if infos else {}
                result = {
                    "is_available": data.get("is_available", False),
                    "total_balance": float(first.get("total_balance", 0)),
                    "granted_balance": float(first.get("granted_balance", 0)),
                    "topped_up_balance": float(first.get("topped_up_balance", 0)),
                    "currency": first.get("currency", "CNY"),
                }
                self._last_balance = result
                self._last_fetch_time = now
                return result
            elif resp.status_code == 401:
                return {"error": "API Key 无效或未授权", "code": 401}
            else:
                return {"error": f"请求失败 (HTTP {resp.status_code})", "code": resp.status_code}
        except requests.exceptions.Timeout:
            return {"error": "请求超时，请检查网络连接"}
        except requests.exceptions.ConnectionError:
            return {"error": "网络连接失败，请检查网络"}
        except Exception as e:
            return {"error": f"未知错误: {str(e)}"}

    def send_completion(
        self,
        messages: list,
        model: str = "deepseek-chat",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None

        try:
            resp = self.session.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 401:
                return {"error": "API Key 无效或未授权", "code": 401}
            else:
                return {"error": f"请求失败 (HTTP {resp.status_code})", "code": resp.status_code}
        except requests.exceptions.Timeout:
            return {"error": "请求超时，请检查网络"}
        except requests.exceptions.ConnectionError:
            return {"error": "网络连接失败"}
        except Exception as e:
            return {"error": f"未知错误: {str(e)}"}

    def calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        pricing = {
            "deepseek-chat": {"input": 0.001, "output": 0.002},
            "deepseek-reasoner": {"input": 0.004, "output": 0.016},
        }
        price = pricing.get(model, pricing["deepseek-chat"])
        cost = (prompt_tokens / 1000 * price["input"]) + (completion_tokens / 1000 * price["output"])
        return round(cost, 6)
