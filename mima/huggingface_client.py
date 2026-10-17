from __future__ import annotations

import httpx

print("MIMA HF VERSION 3")

INFERENCE_API_BASE_URL = "https://api-inference.huggingface.co/models"

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
        endpoint = f"{INFERENCE_API_BASE_URL}/{self.model}"
        print(f"Using model: {self.model}")
        print(f"Using endpoint: {endpoint}")
        prompt = "\n\n".join(
            f"{message['role'].capitalize()}: {message['content']}"
            for message in messages
        )
        prompt += "\n\nAssistant:"
        try:
            response = httpx.post(
                endpoint,
                headers={"Authorization": "Bearer " + self.token},
                json={
                    "inputs": prompt,
                    "parameters": {"max_new_tokens": 700},
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
        except (httpx.HTTPError, ValueError) as error:
            print(f"HF Error: {error}")
            raise MimaServiceError(f"Hugging Face inference failed: {error}") from error

        if not isinstance(result, list) or not result:
            raise MimaServiceError("Hugging Face returned an empty answer.")
        output = result[0]
        generated_text = (
            output.get("generated_text") if isinstance(output, dict) else None
        )
        if not isinstance(generated_text, str):
            raise MimaServiceError("Hugging Face returned an unsupported answer format.")
        if not generated_text.strip():
            raise MimaServiceError("Hugging Face returned an empty answer.")
        return generated_text
