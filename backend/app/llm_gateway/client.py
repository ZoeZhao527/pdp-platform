import re
import time
from dataclasses import dataclass
from typing import Any


class LLMProviderError(Exception):
    pass


@dataclass
class LLMResult:
    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    cost: float = 0.0


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, model: str, provider: str = "openai") -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.provider = provider

    def complete(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 800,
        response_format: dict | None = None,
    ) -> LLMResult:
        start = time.monotonic()
        if not self.api_key and self.provider not in {"ollama", "local"}:
            return self._local_echo(messages)

        try:
            from openai import OpenAI

            # Normalize messages: some providers (DeepSeek, Qwen) don't
            # support content-as-list (vision API format).  Flatten to string.
            norm_messages = []
            for m in messages:
                c = m.get("content")
                if isinstance(c, list):
                    parts = []
                    for item in c:
                        if isinstance(item, dict) and item.get("type") == "text":
                            parts.append(item.get("text", ""))
                        elif isinstance(item, str):
                            parts.append(item)
                    c = "\n".join(parts)
                norm_messages.append({"role": m.get("role", "user"), "content": c or ""})

            client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key or "ollama",
                timeout=300,
                max_retries=1,
            )
            kwargs: dict[str, Any] = dict(
                model=self.model,
                messages=norm_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if response_format:
                kwargs["response_format"] = response_format
            resp = client.chat.completions.create(**kwargs)
            content = (resp.choices[0].message.content or "").strip()
            msg = resp.choices[0].message
            reasoning = getattr(msg, "reasoning_content", None) or ""

            # Reasoning models (GLM-5.2, etc.) split output across content and
            # reasoning_content.  If content is empty, use reasoning_content.
            if not content and reasoning:
                content = reasoning.strip()
            # Strip markdown code fences
            if content.startswith("```"):
                lines = content.split("\n", 1)
                content = lines[1] if len(lines) > 1 else content[3:]
            if content.endswith("```"):
                content = content[:-3].strip()

            usage = resp.usage
            return LLMResult(
                content=content,
                model=self.model,
                provider=self.provider,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                latency_ms=int((time.monotonic() - start) * 1000),
                cost=0.0,
            )
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(str(exc)) from exc

    def _local_echo(self, messages: list[dict[str, str]]) -> LLMResult:
        prompt_tokens = sum(len(m.get("content", "")) for m in messages) // 2
        return LLMResult(
            content="[本地演示模式] 未配置可用的 LLM API Key，请配置后重试。",
            model=self.model,
            provider="local-echo",
            prompt_tokens=prompt_tokens,
            completion_tokens=10,
            latency_ms=1,
        )
