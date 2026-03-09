"""Ollama service wrapper for local LLM inference.

Manages Ollama client lifecycle, health checks, structured output generation,
and GPU memory management via model unloading. All inference runs locally
to comply with PRV-01 (no patient data leaves the machine).
"""

import logging

from ollama import Client, ResponseError

logger = logging.getLogger(__name__)


class OllamaService:
    """Manages Ollama client interactions for clinical extraction.

    Provides health checks (is_available, is_model_ready), structured JSON
    generation via Pydantic schema, and model unloading to free GPU memory.
    """

    def __init__(self, host: str, model: str) -> None:
        self._client = Client(host=host)
        self._model = model

    def is_available(self) -> bool:
        """Check if the Ollama server is reachable."""
        try:
            self._client.list()
            return True
        except Exception:
            return False

    def is_model_ready(self) -> bool:
        """Check if the configured model is pulled and available."""
        try:
            self._client.show(self._model)
            return True
        except ResponseError:
            return False

    def generate_structured(
        self,
        system_prompt: str,
        user_content: str,
        schema: dict,
        temperature: float = 0.0,
        num_ctx: int = 8192,
    ) -> str:
        """Generate structured output conforming to a JSON schema.

        Prepends /nothink to user content to disable Qwen3 thinking mode.
        Returns raw JSON string for caller to validate with Pydantic.
        """
        response = self._client.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"/nothink\n\n{user_content}"},
            ],
            format=schema,
            options={"temperature": temperature, "num_ctx": num_ctx},
        )
        return response.message.content

    def unload(self) -> None:
        """Unload model from GPU memory (keep_alive=0).

        Does not raise on failure -- logs warning instead.
        """
        try:
            self._client.chat(
                model=self._model, messages=[], keep_alive=0
            )
            logger.info("Ollama model %s unloaded", self._model)
        except Exception as e:
            logger.warning("Failed to unload model %s: %s", self._model, e)
