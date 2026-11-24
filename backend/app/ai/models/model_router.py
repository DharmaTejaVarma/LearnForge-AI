import time
from typing import Optional, Dict, Any
from app.core.config import settings
from app.core.logging import logger
from app.ai.models.local_model import LocalModelClient
from app.ai.models.cloud_model import CloudModelClient

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

    async def get_providers_health(self) -> Dict[str, Any]:
        local_h = await self.local_client.check_health()
        cloud_h = await self.cloud_client.check_health()
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
    ) -> Dict[str, Any]:
        preferred_target = ROUTING_MAP.get(task_type, settings.DEFAULT_LLM_PROVIDER)
        start_time = time.time()
        provider_used = preferred_target
        response_text = ""

        # Route logic
        if preferred_target == "cloud":
            cloud_status = await self.cloud_client.check_health()
            if cloud_status["configured"]:
                try:
                    response_text = await self.cloud_client.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    provider_used = "cloud:openai"
                except Exception as e:
                    logger.warning(f"Cloud provider failed for task '{task_type}', attempting local fallback: {e}")
                    response_text = await self.local_client.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        format=format,
                    )
                    provider_used = "local:ollama (fallback)"
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
        logger.info(f"Generated response for task '{task_type}' via {provider_used} in {latency_ms}ms")

        return {
            "content": response_text,
            "provider_used": provider_used,
            "task_type": task_type,
            "latency_ms": latency_ms,
        }

# Global singleton router
model_router = ModelRouter()
