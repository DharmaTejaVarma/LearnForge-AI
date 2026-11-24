from typing import Optional, Dict, Any
from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.core.logging import logger

class CloudModelClient:
    """Client for OpenAI API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.DEFAULT_MODEL
        self._client = None

    def _get_client(self):
        if not self.api_key:
            raise BadRequestException("OpenAI API key is not configured in backend/.env")
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def check_health(self) -> Dict[str, Any]:
        configured = bool(self.api_key and len(self.api_key) > 8 and not self.api_key.startswith("your_"))
        return {
            "configured": configured,
            "model": self.model,
            "provider": "OpenAI"
        }

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ) -> str:
        client = self._get_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise BadRequestException(f"Cloud AI generation failed: {str(e)}")
