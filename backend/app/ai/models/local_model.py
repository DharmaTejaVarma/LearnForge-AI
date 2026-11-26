"""Local Ollama client backed by unified OllamaProvider."""
from typing import Optional, Dict, Any, AsyncIterator
from app.ai.models.provider import OllamaProvider


class LocalModelClient(OllamaProvider):
    """Backward-compatible wrapper around OllamaProvider."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        super().__init__(base_url=base_url, model=model)

    async def check_health(self) -> Dict[str, Any]:
        h = await super().health_check()
        return {
            "online": h.get("online", False),
            "engine": h.get("engine", "ollama"),
            "configured_model": h.get("configured_model", self.model),
            "active_model": h.get("active_model", self.model),
            "model_installed": h.get("model_installed", False),
            "installed_models": h.get("installed_models", []),
        }
