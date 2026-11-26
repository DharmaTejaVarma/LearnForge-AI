from typing import Optional, Dict, Any, List, Tuple
from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.core.logging import logger


class CloudModelClient:
    """Multi-provider cloud LLM client (Groq, Gemini, OpenRouter, OpenAI)."""

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
            try:
                client = self._get_client(name, key, base_url)
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                last_err = e
                logger.warning(f"{name} API call failed: {e}")

        logger.error(f"Cloud AI call failed across all configured providers: {last_err}")
        raise BadRequestException(f"Cloud AI generation failed: {str(last_err)}")
