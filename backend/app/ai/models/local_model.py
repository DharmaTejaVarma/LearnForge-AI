import httpx
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.core.logging import logger

class LocalModelClient:
    """Client for local Ollama instance running Qwen with dynamic model resolution."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.LOCAL_MODEL

    async def check_health(self) -> Dict[str, Any]:
        """Probes the Ollama server for availability and installed models."""
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    has_model = any(self.model in m for m in models)
                    active_model = self.model if has_model else (models[0] if models else self.model)
                    return {
                        "online": True,
                        "configured_model": self.model,
                        "active_model": active_model,
                        "model_installed": has_model or len(models) > 0,
                        "installed_models": models,
                    }
        except Exception as e:
            logger.debug(f"Ollama health probe offline: {e}")
        return {
            "online": False,
            "configured_model": self.model,
            "active_model": self.model,
            "model_installed": False,
            "installed_models": []
        }

    async def get_active_model(self) -> str:
        """Dynamically resolves the best matching model from Ollama."""
        health = await self.check_health()
        if not health["online"]:
            return self.model

        installed: List[str] = health.get("installed_models", [])
        if not installed:
            return self.model

        # 1. Exact or prefix match with configured model
        for m in installed:
            if self.model in m or m.startswith(self.model):
                return m

        # 2. Check for any qwen variant
        for m in installed:
            if "qwen" in m.lower():
                return m

        # 3. Fall back to the first installed model
        return installed[0]

    async def generate(
        self,
        prompt: Any,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1200,
        format: Optional[str] = None,
    ) -> str:
        active_model = await self.get_active_model()

        if isinstance(prompt, list):
            url = f"{self.base_url}/api/chat"
            messages = list(prompt)
            if system_prompt and not any(isinstance(m, dict) and m.get("role") == "system" for m in messages):
                messages = [{"role": "system", "content": system_prompt}] + messages
            payload: Dict[str, Any] = {
                "model": active_model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }
        else:
            url = f"{self.base_url}/api/generate"
            payload: Dict[str, Any] = {
                "model": active_model,
                "prompt": str(prompt),
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }
            if system_prompt:
                payload["system"] = system_prompt

        if format:
            payload["format"] = format

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code != 200:
                    raise BadRequestException(f"Ollama returned error: {res.text}")
                data = res.json()
                if "message" in data:
                    return data.get("message", {}).get("content", "").strip()
                return data.get("response", "").strip()
        except httpx.ConnectError:
            raise BadRequestException(
                f"Local Ollama service is unreachable at {self.base_url}. "
                f"Ensure Ollama is running ('ollama serve') and model is pulled ('ollama pull {self.model}')"
            )
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise BadRequestException(f"Local AI generation failed: {str(e)}")
