"""Ollama service wrapper for local LLM inference.

Manages Ollama client lifecycle, health checks, structured output generation,
and GPU memory management via model unloading. All inference runs locally
to comply with PRV-01 (no patient data leaves the machine).
"""

import copy
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

    @staticmethod
    def _dereference_schema(schema: dict) -> dict:
        """Inline $ref/$defs and strip unsupported keys for Ollama.

        Ollama's structured output requires flat schemas without $ref,
        pattern, title, or description annotations.
        """
        schema = copy.deepcopy(schema)
        defs = schema.pop("$defs", {})

        _strip_keys = {"title", "pattern"}

        def _resolve(node: object, is_properties_value: bool = False) -> object:
            if isinstance(node, dict):
                if "$ref" in node:
                    ref_name = node["$ref"].split("/")[-1]
                    return _resolve(defs[ref_name], is_properties_value)
                result = {}
                for k, v in node.items():
                    if k in _strip_keys:
                        continue
                    if k == "description" and not is_properties_value:
                        continue
                    in_props = k == "properties"
                    result[k] = (
                        {pk: _resolve(pv, True) for pk, pv in v.items()}
                        if in_props and isinstance(v, dict)
                        else _resolve(v, False)
                    )
                return result
            if isinstance(node, list):
                return [_resolve(item, False) for item in node]
            return node

        return _resolve(schema)  # type: ignore[return-value]

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
        Dereferences $ref/$defs since Ollama requires flat schemas.
        Returns raw JSON string for caller to validate with Pydantic.
        """
        resolved_schema = self._dereference_schema(schema)
        response = self._client.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"/nothink\n\n{user_content}"},
            ],
            format=resolved_schema,
            options={"temperature": temperature, "num_ctx": num_ctx},
        )
        return response.message.content

    def generate(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.0,
        num_ctx: int = 2048,
    ) -> str:
        """Generate plain text (non-structured) output.

        Used for lightweight classification tasks like appointment type
        detection where a single word response is expected.
        Prepends /nothink to user content to disable Qwen3 thinking mode.
        """
        response = self._client.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"/nothink\n\n{user_content}"},
            ],
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
