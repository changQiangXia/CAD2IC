"""Per-task API call, token, and wall-time guard for Plan 2."""

import os
import time

from pydantic import PrivateAttr

from mage.gen_config import DeepSeekOpenAI


class BudgetExceeded(RuntimeError):
    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind


class BudgetedDeepSeekOpenAI(DeepSeekOpenAI):
    _max_calls: int = PrivateAttr(default=120)
    _max_tokens: int = PrivateAttr(default=500000)
    _max_seconds: float = PrivateAttr(default=1800.0)
    _calls: int = PrivateAttr(default=0)
    _tokens: int = PrivateAttr(default=0)
    _started: float = PrivateAttr(default=0.0)
    _exceeded_kind: str = PrivateAttr(default="")

    def reset_budget(self) -> None:
        self._calls = 0
        self._tokens = 0
        self._started = time.monotonic()
        self._exceeded_kind = ""

    def _raise_budget(self, kind: str, detail: str) -> None:
        self._exceeded_kind = kind
        raise BudgetExceeded(kind, detail)

    def _check_call_budget(self) -> None:
        if time.monotonic() - self._started >= self._max_seconds:
            self._raise_budget("timeout", "Task exceeded 1800 seconds")
        if self._calls >= self._max_calls:
            self._raise_budget(
                "api_budget_exhausted", "Task exceeded 120 API calls"
            )
        self._calls += 1

    def _record_usage(self, response) -> None:
        raw = getattr(response, "raw", None)
        usage = getattr(raw, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        self._tokens += prompt_tokens + completion_tokens
        if self._tokens > self._max_tokens:
            self._raise_budget(
                "token_budget_exhausted",
                f"Task exceeded {self._max_tokens} input/output tokens",
            )

    def chat(self, *args, **kwargs):
        self._check_call_budget()
        response = super().chat(*args, **kwargs)
        self._record_usage(response)
        return response

    async def achat(self, *args, **kwargs):
        self._check_call_budget()
        response = await super().achat(*args, **kwargs)
        self._record_usage(response)
        return response

    def budget_snapshot(self) -> dict:
        return {
            "api_calls": self._calls,
            "tokens": self._tokens,
            "max_api_calls": self._max_calls,
            "max_tokens": self._max_tokens,
            "max_seconds": self._max_seconds,
            "elapsed_seconds": time.monotonic() - self._started,
            "exceeded_kind": self._exceeded_kind,
        }


def build_budgeted_llm(max_tokens: int = 8192) -> BudgetedDeepSeekOpenAI:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")
    api_base = os.environ.get(
        "DEEPSEEK_API_BASE_URL", "https://api.deepseek.com"
    )
    return BudgetedDeepSeekOpenAI(
        model="deepseek-flash",
        api_key=api_key,
        api_base=api_base,
        max_tokens=max_tokens,
        max_retries=0,
        additional_kwargs={"extra_body": {"thinking": {"type": "disabled"}}},
    )
