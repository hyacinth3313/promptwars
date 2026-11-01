from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional, Type, TypeVar

from groq import AsyncGroq, APIError, AuthenticationError, RateLimitError
from pydantic import BaseModel, ValidationError

from config import settings

logger = logging.getLogger("ai_client")

T = TypeVar("T", bound=BaseModel)


class GroqClientError(Exception):
    """Base exception for Groq client operations."""
    pass


class GroqConfigurationError(GroqClientError):
    """Raised when Groq API key is missing or invalid."""
    pass


class GroqGenerationError(GroqClientError):
    """Raised when generation or schema validation fails after retry."""
    pass


class GroqClient:
    """
    Asynchronous Groq client wrapper for structured and text generations
    using 100% free-tier models on Groq.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.groq_api_key
        self.model = model if model is not None else settings.groq_model
        self._async_client: Optional[AsyncGroq] = None

    @property
    def is_configured(self) -> bool:
        """Verify if a valid, non-placeholder Groq API key is present."""
        return bool(
            self.api_key
            and self.api_key.strip()
            and not self.api_key.startswith("gsk_your_free")
        )

    def _get_client(self) -> AsyncGroq:
        """Lazily initialize and return the AsyncGroq client."""
        if not self.is_configured:
            raise GroqConfigurationError(
                "GROQ_API_KEY is not configured or using a placeholder. "
                "Obtain a free key at https://console.groq.com/keys and set GROQ_API_KEY in your .env file."
            )
        if self._async_client is None:
            self._async_client = AsyncGroq(api_key=self.api_key.strip())
        return self._async_client

    @staticmethod
    def clean_json_response(raw_text: str) -> str:
        """
        Strip markdown code blocks, backticks, and extraneous prose
        to extract pure JSON string.
        """
        cleaned = raw_text.strip()

        # Match ```json ... ``` or ``` ... ```
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        elif cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        # If there's still text before the first '{' or after the last '}', trim it
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            cleaned = cleaned[first_brace : last_brace + 1]

        return cleaned

    async def generate_structured(
        self,
        system: str,
        user: str,
        schema: Type[T],
        temperature: float = 0.2,
    ) -> T:
        """
        Generate strict, type-safe structured output conforming to a Pydantic schema.
        Automatically retries once if JSON decoding or schema validation fails.

        Args:
            system: System instructions describing role and task.
            user: User prompt including context and requirements.
            schema: The target Pydantic BaseModel class.
            temperature: Sampling temperature (default 0.2 for deterministic formatting).

        Returns:
            An instance of the provided schema model.

        Raises:
            GroqConfigurationError: If API key is not configured.
            GroqGenerationError: If output fails validation after retry.
            GroqClientError: For network or provider errors.
        """
        client = self._get_client()
        schema_json = json.dumps(schema.model_json_schema(), indent=2)

        augmented_system = (
            f"{system}\n\n"
            "CRITICAL FORMATTING INSTRUCTIONS:\n"
            "- Return ONLY valid JSON. No markdown, no explanation, no backticks, no code fences.\n"
            "- The output must conform strictly to the following JSON Schema:\n"
            f"{schema_json}"
        )

        messages = [
            {"role": "system", "content": augmented_system},
            {"role": "user", "content": user},
        ]

        logger.info(
            f"Invoking Groq model '{self.model}' for structured schema '{schema.__name__}'..."
        )

        # First attempt
        raw_output = ""
        try:
            completion = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            raw_output = completion.choices[0].message.content or "{}"
            cleaned_json = self.clean_json_response(raw_output)
            return schema.model_validate_json(cleaned_json)

        except (json.JSONDecodeError, ValidationError) as validation_err:
            logger.warning(
                f"Groq structured validation failed on attempt 1 for '{schema.__name__}': {validation_err}. "
                "Executing automatic retry..."
            )

            # Retry once with explicit error feedback
            retry_messages = [
                {"role": "system", "content": augmented_system},
                {"role": "user", "content": user},
                {"role": "assistant", "content": raw_output},
                {
                    "role": "user",
                    "content": (
                        f"Your previous output failed JSON validation with the following error: {validation_err}\n"
                        "Please regenerate the response now. Return ONLY valid JSON adhering strictly to the JSON schema. "
                        "Do not include any prose, markdown backticks, or explanation."
                    ),
                },
            ]

            try:
                retry_completion = await client.chat.completions.create(
                    model=self.model,
                    messages=retry_messages,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                )
                retry_raw = retry_completion.choices[0].message.content or "{}"
                retry_cleaned = self.clean_json_response(retry_raw)
                validated = schema.model_validate_json(retry_cleaned)
                logger.info(
                    f"Retry succeeded for '{schema.__name__}' with model '{self.model}'."
                )
                return validated

            except Exception as retry_err:
                logger.error(
                    f"Retry failed for '{schema.__name__}': {retry_err}. Raw output was: {raw_output[:300]}"
                )
                raise GroqGenerationError(
                    f"Failed to generate valid structured data for {schema.__name__} after retry: {retry_err}"
                ) from retry_err

        except AuthenticationError as auth_err:
            logger.error(f"Groq Authentication error: {auth_err}")
            raise GroqConfigurationError(
                f"Groq authentication failed. Please verify GROQ_API_KEY: {auth_err}"
            ) from auth_err

        except RateLimitError as rate_err:
            logger.error(f"Groq Rate limit exceeded: {rate_err}")
            raise GroqClientError(
                f"Groq rate limit reached on free tier: {rate_err}"
            ) from rate_err

        except APIError as api_err:
            logger.error(f"Groq API error: {api_err}")
            raise GroqClientError(f"Groq API error: {api_err}") from api_err

        except Exception as general_err:
            logger.error(f"Unexpected error in GroqClient: {general_err}", exc_info=True)
            raise GroqClientError(f"AI generation failed: {general_err}") from general_err

    async def generate_text(
        self,
        system: str,
        user: str,
        temperature: float = 0.4,
    ) -> str:
        """
        Generate freeform conversational text for chat or consultative queries.
        """
        client = self._get_client()
        try:
            completion = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
            )
            return completion.choices[0].message.content or ""
        except AuthenticationError as auth_err:
            raise GroqConfigurationError(f"Invalid Groq credentials: {auth_err}") from auth_err
        except Exception as exc:
            logger.error(f"Groq generate_text failed: {exc}")
            raise GroqClientError(f"Chat generation failed: {exc}") from exc


# Shared module singleton instance
ai_client = GroqClient()

