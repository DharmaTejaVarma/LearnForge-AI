import asyncio
import re
import time
from typing import Optional, Dict, Any, List, Tuple
from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.core.logging import logger


class CloudModelClient:
    """Multi-provider cloud LLM client (Groq, Gemini, OpenRouter, OpenAI)."""

    _groq_rr_idx: int = 0
    _groq_cooldown: Dict[str, float] = {}

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.DEFAULT_MODEL
        self._clients: Dict[str, Any] = {}

    @staticmethod
    def _is_valid_key(key: Optional[str]) -> bool:
        return bool(key and len(key.strip()) > 8 and not key.strip().startswith("your_"))

    def _configured_providers(self) -> List[Tuple[str, str, str, Optional[str]]]:
        """Return ordered list of (provider_name, api_key, model, base_url) for fast cloud inference."""
        providers: List[Tuple[str, str, str, Optional[str]]] = []
        if self._is_valid_key(settings.GROQ_API_KEY):
            providers.append(("Groq", settings.GROQ_API_KEY, settings.GROQ_MODEL, "https://api.groq.com/openai/v1"))
        if self._is_valid_key(settings.GEMINI_API_KEY):
            providers.append(("Gemini", settings.GEMINI_API_KEY, settings.GEMINI_MODEL, "https://generativelanguage.googleapis.com/v1beta/openai/"))
        if self._is_valid_key(settings.OPENROUTER_API_KEY):
            providers.append(("OpenRouter", settings.OPENROUTER_API_KEY, settings.OPENROUTER_MODEL, "https://openrouter.ai/api/v1"))
        if self._is_valid_key(self.api_key):
            providers.append(("OpenAI", self.api_key, self.model, None))
        return providers

    def _get_client(self, provider_name: str, api_key: str, base_url: Optional[str]):
        if provider_name not in self._clients:
            from openai import AsyncOpenAI
            kwargs: Dict[str, Any] = {"api_key": api_key, "max_retries": 0}
            if base_url:
                kwargs["base_url"] = base_url
            self._clients[provider_name] = AsyncOpenAI(**kwargs)
        return self._clients[provider_name]

    async def check_health(self) -> Dict[str, Any]:
        providers = self._configured_providers()
        if not providers:
            return {"configured": False, "model": self.model, "provider": "None"}
        name, _, model, _ = providers[0]
        return {
            "configured": True,
            "model": model,
            "provider": name,
        }

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ) -> str:
        providers = self._configured_providers()
        if not providers:
            raise BadRequestException("No cloud API key configured in backend/.env")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        last_err: Optional[Exception] = None
        for name, key, model, base_url in providers:
            client = self._get_client(name, key, base_url)
            eff_max_tokens = min(max_tokens, 600) if name == "Groq" else max_tokens
            # Round-robin across fast Groq models (each has its own 8k TPM bucket) to avoid 429s & maximize speed
            models_to_try = [model]
            if name == "Groq":
                now_m = time.monotonic()
                pool = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b", model]
                deduped: List[str] = []
                for p in pool:
                    if p not in deduped and CloudModelClient._groq_cooldown.get(p, 0.0) <= now_m:
                        deduped.append(p)
                if not deduped:
                    deduped = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
                idx = CloudModelClient._groq_rr_idx % len(deduped)
                CloudModelClient._groq_rr_idx += 1
                models_to_try = deduped[idx:] + deduped[:idx]

            rate_limit_wait: Optional[float] = None
            rate_limit_model: Optional[str] = None
            for m in models_to_try:
                try:
                    req_kwargs: Dict[str, Any] = {
                        "model": m,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": eff_max_tokens,
                    }
                    if name == "Groq" and "gpt-oss" in m:
                        req_kwargs["extra_body"] = {"reasoning_effort": "low"}
                    response = await client.chat.completions.create(**req_kwargs)
                    return response.choices[0].message.content.strip()
                except Exception as e:
                    last_err = e
                    err_str = str(e)
                    logger.warning(f"{name} ({m}) API call failed: {e}")
                    if "429" in err_str or "rate_limit" in err_str.lower():
                        if "tokens per day" in err_str.lower() or "tpd" in err_str.lower():
                            CloudModelClient._groq_cooldown[m] = time.monotonic() + 180.0
                        match = re.search(r"try again in ([0-9.]+)s", err_str, re.IGNORECASE)
                        if match:
                            wait_s = min(float(match.group(1)) + 0.25, 18.0)
                            if rate_limit_wait is None or wait_s < rate_limit_wait:
                                rate_limit_wait = wait_s
                                rate_limit_model = m
                    else:
                        break  # Non-rate-limit error (auth/network), move to next provider

            # Wait for the model with the shortest reset (up to 18s) instead of falling back to ~300s local CPU Ollama.
            if name == "Groq" and rate_limit_wait is not None and rate_limit_model:
                try:
                    await asyncio.sleep(rate_limit_wait)
                    retry_kwargs: Dict[str, Any] = {
                        "model": rate_limit_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": eff_max_tokens,
                    }
                    if "gpt-oss" in rate_limit_model:
                        retry_kwargs["extra_body"] = {"reasoning_effort": "low"}
                    response = await client.chat.completions.create(**retry_kwargs)
                    return response.choices[0].message.content.strip()
                except Exception as e:
                    last_err = e
                    logger.warning(f"{name} ({rate_limit_model}) retry after {rate_limit_wait:.2f}s failed: {e}")

        logger.error(f"Cloud AI call failed across all configured providers: {last_err}")
        if len(providers) > 1 and any(p[0] == "Gemini" for p in providers):
            # Preserve Gemini transient errors instead of letting a secondary exhausted OpenAI key poison startup probe
            raise BadRequestException(f"Cloud AI generation failed (Gemini primary): {providers[0][0]} unavailable")
        raise BadRequestException(f"Cloud AI generation failed: {str(last_err)}")
