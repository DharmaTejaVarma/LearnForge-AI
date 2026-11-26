import math
import time
from collections import deque
from typing import Optional, Dict, Any, Deque
from app.core.config import settings
from app.core.logging import logger
from app.ai.models.local_model import LocalModelClient
from app.ai.models.cloud_model import CloudModelClient
from app.ai.models.provider import OpenAICompatibleProvider

# Task Routing Rules
ROUTING_MAP = {
    # Routine / local tasks -> Local Qwen (Ollama)
    "summary": "local",
    "flashcard": "local",
    "mcq": "local",
    "topic_classification": "local",

    # Complex reasoning tasks -> Cloud OpenAI (with fallback to Local Qwen)
    "course_outline": "cloud",
    "lesson_content": "cloud",
    "tutor_socratic": "cloud",
    "assessment_eval": "cloud",
}

class ModelRouter:
    """Centralized Model Router governing Local (Ollama Qwen) and Cloud (OpenAI) routing."""

    def __init__(self):
        self.local_client = LocalModelClient()
        self.cloud_client = CloudModelClient()
        self.llama_cpp_client = (
            OpenAICompatibleProvider("llama_cpp", settings.LLAMA_CPP_BASE_URL, "not-needed", settings.LLAMA_CPP_MODEL)
            if settings.LLAMA_CPP_BASE_URL
            else None
        )
        self.vllm_client = (
            OpenAICompatibleProvider("vllm", settings.VLLM_BASE_URL, "not-needed", settings.VLLM_MODEL)
            if settings.VLLM_BASE_URL
            else None
        )
        self._cloud_disabled_reason: Optional[str] = None
        self._latencies_ms: Deque[float] = deque(maxlen=200)
        self._stats: Dict[str, int] = {
            "total_requests": 0,
            "local_requests": 0,
            "cloud_requests": 0,
            "fallback_count": 0,
            "error_count": 0,
            "estimated_input_tokens": 0,
            "estimated_output_tokens": 0,
        }

    def is_local_only(self) -> bool:
        """Return True if no usable cloud provider is configured or quota is exhausted."""
        if self._cloud_disabled_reason:
            return True
        api_key = getattr(self.cloud_client, "api_key", "") or ""
        return not (len(api_key) > 8 and not api_key.startswith("your_"))

    async def probe_cloud_once(self) -> None:
        """Probe OpenAI once on startup so exhausted/invalid keys disable cloud immediately."""
        if self._cloud_disabled_reason:
            return
        cloud_status = await self.cloud_client.check_health()
        if not cloud_status.get("configured"):
            return
        try:
            await self.cloud_client.generate(prompt="ok", max_tokens=1, temperature=0.0)
            logger.info(f"Cloud OpenAI probe succeeded ({self.cloud_client.model})")
        except Exception as e:
            err_str = str(e)
            if self._is_fatal_cloud_error(err_str):
                self._cloud_disabled_reason = err_str
                logger.warning(f"Disabling cloud provider at startup due to quota/auth error; using local Ollama: {err_str}")
            else:
                logger.warning(f"Cloud OpenAI startup probe failed (will retry on demand): {err_str}")

    @staticmethod
    def _is_fatal_cloud_error(err_msg: str) -> bool:
        lower = err_msg.lower()
        fatal_markers = (
            "credit_balance_exhausted",
            "insufficient_quota",
            "invalid_api_key",
            "incorrect api key",
            "error code: 401",
            "error code: 403",
        )
        return any(m in lower for m in fatal_markers)

    async def get_providers_health(self) -> Dict[str, Any]:
        local_h = await self.local_client.check_health()
        cloud_h = await self.cloud_client.check_health()
        if self._cloud_disabled_reason:
            cloud_h["disabled_reason"] = self._cloud_disabled_reason
        return {
            "local_ollama": local_h,
            "cloud_openai": cloud_h,
            "default_provider": settings.DEFAULT_LLM_PROVIDER,
        }

    async def generate(
        self,
        prompt: str,
        task_type: str = "summary",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        format: Optional[str] = None,
        allow_local_fallback: bool = True,
    ) -> Dict[str, Any]:
        preferred_target = ROUTING_MAP.get(task_type, settings.DEFAULT_LLM_PROVIDER)
        start_time = time.time()
        provider_used = preferred_target
        response_text = ""

        # Route logic
        if preferred_target == "cloud":
            cloud_status = await self.cloud_client.check_health()
            if cloud_status["configured"] and not self._cloud_disabled_reason:
                try:
                    response_text = await self.cloud_client.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    provider_used = "cloud:openai"
                except Exception as e:
                    if self._is_fatal_cloud_error(str(e)):
                        self._cloud_disabled_reason = str(e)
                        logger.warning(f"Disabling cloud provider for this session due to quota/auth error; using local Ollama: {e}")
                    else:
                        logger.warning(f"Cloud provider failed for task '{task_type}', attempting local fallback: {e}")
                    if not allow_local_fallback:
                        raise
                    response_text = await self.local_client.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        format=format,
                    )
                    provider_used = "local:ollama (fallback)"
            else:
                if self._cloud_disabled_reason:
                    logger.debug(f"Cloud provider disabled ({self._cloud_disabled_reason}); routing '{task_type}' to local Ollama")
                else:
                    logger.info(f"OpenAI not configured, routing '{task_type}' to local Ollama Qwen")
                response_text = await self.local_client.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    format=format,
                )
                provider_used = "local:ollama"
        else:
            response_text = await self.local_client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                format=format,
            )
            provider_used = "local:ollama"

        latency_ms = round((time.time() - start_time) * 1000, 2)
        self._record_telemetry(
            provider_used=provider_used,
            latency_ms=latency_ms,
            prompt_text=str(prompt),
            response_text=response_text,
        )
        logger.info(f"Generated response for task '{task_type}' via {provider_used} in {latency_ms}ms")

        return {
            "content": response_text,
            "provider_used": provider_used,
            "task_type": task_type,
            "latency_ms": latency_ms,
        }

    def _record_telemetry(
        self,
        provider_used: str,
        latency_ms: float,
        prompt_text: str,
        response_text: str,
    ) -> None:
        self._stats["total_requests"] += 1
        self._latencies_ms.append(latency_ms)
        if "cloud" in provider_used:
            self._stats["cloud_requests"] += 1
        else:
            self._stats["local_requests"] += 1
        if "fallback" in provider_used:
            self._stats["fallback_count"] += 1
        self._stats["estimated_input_tokens"] += max(1, len(prompt_text) // 4)
        self._stats["estimated_output_tokens"] += max(1, len(response_text) // 4)

    def get_metrics(self) -> Dict[str, Any]:
        """Return safe runtime latency and token metrics for observability."""
        latencies = sorted(self._latencies_ms)
        avg_ms = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        p95_idx = min(len(latencies) - 1, max(0, int(math.ceil(0.95 * len(latencies))) - 1))
        p95_ms = round(latencies[p95_idx], 2) if latencies else 0.0
        return {
            **self._stats,
            "avg_latency_ms": avg_ms,
            "p95_latency_ms": p95_ms,
            "local_only_mode": self.is_local_only(),
        }

# Global singleton router
model_router = ModelRouter()
