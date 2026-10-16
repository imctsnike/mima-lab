from __future__ import annotations

import httpx
from huggingface_hub import InferenceClient
from huggingface_hub.utils import HfHubHTTPError


class MimaServiceError(RuntimeError):
    pass


class HuggingFaceAssistant:
    def __init__(self, token: str, model: str, timeout: float = 45) -> None:
        self.token = token
        self.model = model
        self.timeout = timeout

    def answer(self, messages: list[dict[str, str]]) -> str:
        if not self.token:
            raise MimaServiceError(
                "Hugging Face is not configured. Set the HF_TOKEN environment variable."
            )
        client = InferenceClient(
            model=self.model,
            token=self.token,
            timeout=self.timeout,
        )
        try:
            response = client.chat_completion(
                messages=messages,
                max_tokens=700,
                temperature=0.2,
            )
        except (HfHubHTTPError, httpx.HTTPError) as error:
            raise MimaServiceError(f"Hugging Face inference failed: {error}") from error
        if not response.choices or not response.choices[0].message.content:
            raise MimaServiceError("Hugging Face returned an empty answer.")
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise MimaServiceError("Hugging Face returned an unsupported answer format.")
        return content
