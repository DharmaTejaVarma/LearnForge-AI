"""Unified LLM Provider abstraction for LearnForge AI.

Supports Ollama, llama.cpp (llama-server HTTP), vLLM, and OpenAI-compatible
endpoints (Groq, Gemini, OpenRouter, OpenAI) behind one async interface.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.core.logging import logger


class LLMProvider(ABC):
    """Abstract base class for all local and remote LLM inference backends."""

    @abstractmethod
    async def generate(
        self,
        prompt: Any,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        format: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> str:
        """Generate a complete text response."""

    @abstractmethod
    async def generate_stream(
        self,
        prompt: Any,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        request_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Stream generated text chunks as they arrive."""

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Return live availability and model readiness; never fake online=True."""

    @abstractmethod
    async def get_model_info(self) -> Dict[str, Any]:
        """Return active model name, engine type, and context settings."""

    def estimate_tokens(self, text: str) -> int:
        """Fast heuristic token estimate (~4 chars per token for English/code)."""
        if not text:
            return 0
        return max(1, (len(text) + 3) // 4)

    @abstractmethod
    async def cancel_generation(self, request_id: str) -> bool:
        """Cancel an in-flight generation by request_id if supported."""


class OllamaProvider(LLMProvider):
    """Ollama HTTP adapter with physical-core threading, streaming, and cancellation."""

    _loop_semaphores: Dict[int, asyncio.Semaphore] = {}

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.LOCAL_MODEL
        self._cached_model: Optional[str] = None
        self._cached_model_ts: float = 0.0
        self._inflight: Dict[str, asyncio.Task] = {}

    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        """Serialize CPU Ollama inference per event loop to prevent thrashing."""
        loop = asyncio.get_running_loop()
        loop_id = id(loop)
        sem = cls._loop_semaphores.get(loop_id)
        if sem is None:
            sem = asyncio.Semaphore(1)
            cls._loop_semaphores[loop_id] = sem
        return sem

    @staticmethod
    def _optimal_threads() -> int:
        logical = os.cpu_count() or 8
        # Physical cores (~logical // 2 on SMT CPUs) avoid L1/L2 cache contention
        return max(4, min(logical, max(4, logical // 2)))

    @staticmethod
    def _match_installed_model(target: str, installed: List[str]) -> Optional[str]:
        """Exact match (or `:latest` if no tag specified) — never silently switch models."""
        if not target or not installed:
            return None
        for m in installed:
            if m == target or (":" not in target and m == f"{target}:latest"):
                return m
        return None

    async def health_check(self) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    models = [m.get("name") for m in res.json().get("models", []) if m.get("name")]
                    matched = self._match_installed_model(self.model, models)
                    return {
                        "online": matched is not None,
                        "engine": "ollama",
                        "configured_model": self.model,
                        "active_model": matched or self.model,
                        "model_installed": matched is not None,
                        "installed_models": models,
                        "error": None if matched else f"Model '{self.model}' not installed. Run: ollama pull {self.model}",
                    }
        except Exception as exc:
            logger.debug(f"Ollama health_check offline: {exc}")
        return {
            "online": False,
            "engine": "ollama",
            "configured_model": self.model,
            "active_model": self.model,
            "model_installed": False,
            "installed_models": [],
            "error": f"Ollama unreachable at {self.base_url}",
        }

    async def get_active_model(self) -> str:
        now = time.monotonic()
        if self._cached_model and (now - self._cached_model_ts) < 60.0:
            return self._cached_model
        health = await self.health_check()
        installed: List[str] = health.get("installed_models", [])
        if not installed and not health.get("online"):
            raise BadRequestException(
                f"Local Ollama service is unreachable at {self.base_url} or no models installed. "
                f"Ensure Ollama is running and run: ollama pull {self.model}"
            )
        matched = self._match_installed_model(self.model, installed)
        if not matched:
            raise BadRequestException(
                f"Configured Ollama model '{self.model}' is not installed "
                f"(installed: {', '.join(installed) or 'none'}). Run: ollama pull {self.model}"
            )
        self._cached_model = matched
        self._cached_model_ts = now
        return matched

    async def get_model_info(self) -> Dict[str, Any]:
        active = await self.get_active_model()
        return {
            "engine": "ollama",
            "model": active,
            "base_url": self.base_url,
            "num_ctx": 2048,
            "num_thread": self._optimal_threads(),
        }

    def _build_payload(
        self,
        active_model: str,
        prompt: Any,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        stream: bool,
        format: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        options = {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": 2048,
            "num_thread": self._optimal_threads(),
        }
        if isinstance(prompt, list):
            url = f"{self.base_url}/api/chat"
            messages = list(prompt)
            if system_prompt and not any(isinstance(m, dict) and m.get("role") == "system" for m in messages):
                messages = [{"role": "system", "content": system_prompt}] + messages
            payload: Dict[str, Any] = {
                "model": active_model,
                "messages": messages,
                "stream": stream,
                "keep_alive": "15m",
                "options": options,
            }
        else:
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": active_model,
                "prompt": str(prompt),
                "stream": stream,
                "keep_alive": "15m",
                "options": options,
            }
            if system_prompt:
                payload["system"] = system_prompt
        if format:
            payload["format"] = format
        return url, payload

    async def generate(
        self,
        prompt: Any,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        format: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> str:
        req_id = request_id or uuid.uuid4().hex
        active_model = await self.get_active_model()
        url, payload = self._build_payload(
            active_model, prompt, system_prompt, temperature, max_tokens, stream=False, format=format
        )

        async def _call() -> str:
            async with self._get_semaphore():
                async with httpx.AsyncClient(timeout=300.0) as client:
                    res = await client.post(url, json=payload)
                    if res.status_code != 200:
                        raise BadRequestException(f"Ollama returned error: {res.text}")
                    data = res.json()
                    if "message" in data:
                        return data.get("message", {}).get("content", "").strip()
                    return data.get("response", "").strip()

        task = asyncio.create_task(_call())
        self._inflight[req_id] = task
        try:
            return await task
        except asyncio.CancelledError:
            raise BadRequestException(f"Generation cancelled ({req_id})")
        except httpx.ConnectError:
            raise BadRequestException(
                f"Local Ollama service is unreachable at {self.base_url}. "
                f"Ensure Ollama is running ('ollama serve')."
            )
        finally:
            self._inflight.pop(req_id, None)

    async def generate_stream(
        self,
        prompt: Any,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        request_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        active_model = await self.get_active_model()
        url, payload = self._build_payload(
            active_model, prompt, system_prompt, temperature, max_tokens, stream=True
        )
        async with self._get_semaphore():
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream("POST", url, json=payload) as res:
                    if res.status_code != 200:
                        raise BadRequestException(f"Ollama stream error: HTTP {res.status_code}")
                    async for line in res.iter_lines():
                        if not line:
                            continue
                        obj = json.loads(line)
                        chunk = obj.get("message", {}).get("content") if "message" in obj else obj.get("response")
                        if chunk:
                            yield chunk

    async def cancel_generation(self, request_id: str) -> bool:
        task = self._inflight.get(request_id)
        if task and not task.done():
            task.cancel()
            return True
        return False


class OpenAICompatibleProvider(LLMProvider):
    """Adapter for llama.cpp (llama-server), vLLM, Groq, Gemini, OpenRouter, or OpenAI."""

    def __init__(
        self,
        engine_name: str,
        base_url: Optional[str],
        api_key: str,
        model: str,
    ):
        self.engine_name = engine_name
        self.base_url = base_url.rstrip("/") if base_url else None
        self.api_key = api_key or "not-needed"
        self.model = model
        self._client = None
        self._inflight: Dict[str, asyncio.Task] = {}

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            kwargs: Dict[str, Any] = {"api_key": self.api_key, "max_retries": 0}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def health_check(self) -> Dict[str, Any]:
        if not self.base_url:
            configured = bool(self.api_key and len(self.api_key) > 8 and not self.api_key.startswith("your_"))
            return {"online": configured, "engine": self.engine_name, "model": self.model}
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/models")
                if res.status_code == 200:
                    return {"online": True, "engine": self.engine_name, "model": self.model}
        except Exception:
            pass
        return {"online": False, "engine": self.engine_name, "model": self.model}

    async def get_model_info(self) -> Dict[str, Any]:
        return {"engine": self.engine_name, "model": self.model, "base_url": self.base_url}

    async def generate(
        self,
        prompt: Any,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        format: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> str:
        req_id = request_id or uuid.uuid4().hex
        messages = list(prompt) if isinstance(prompt, list) else [{"role": "user", "content": str(prompt)}]
        if system_prompt and not any(isinstance(m, dict) and m.get("role") == "system" for m in messages):
            messages = [{"role": "system", "content": system_prompt}] + messages

        async def _call() -> str:
            client = self._get_client()
            res = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return (res.choices[0].message.content or "").strip()

        task = asyncio.create_task(_call())
        self._inflight[req_id] = task
        try:
            return await task
        finally:
            self._inflight.pop(req_id, None)

    async def generate_stream(
        self,
        prompt: Any,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        request_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        messages = list(prompt) if isinstance(prompt, list) else [{"role": "user", "content": str(prompt)}]
        if system_prompt and not any(isinstance(m, dict) and m.get("role") == "system" for m in messages):
            messages = [{"role": "system", "content": system_prompt}] + messages
        client = self._get_client()
        stream = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

    async def cancel_generation(self, request_id: str) -> bool:
        task = self._inflight.get(request_id)
        if task and not task.done():
            task.cancel()
            return True
        return False
