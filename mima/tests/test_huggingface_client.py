from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from huggingface_client import HuggingFaceAssistant, INFERENCE_API_BASE_URL


class HuggingFaceAssistantTests(unittest.TestCase):
    @patch("huggingface_client.httpx.post")
    def test_answer_calls_standard_inference_api(self, post: Mock) -> None:
        response = Mock()
        response.json.return_value = [{"generated_text": "An answer."}]
        post.return_value = response
        messages = [{"role": "user", "content": "What happened?"}]

        model = "google/flan-t5-large"
        answer = HuggingFaceAssistant("test-token", model, timeout=12).answer(messages)

        self.assertEqual(answer, "An answer.")
        post.assert_called_once_with(
            f"{INFERENCE_API_BASE_URL}/{model}",
            headers={"Authorization": "Bearer test-token"},
            json={
                "inputs": "User: What happened?\n\nAssistant:",
                "parameters": {"max_new_tokens": 700},
            },
            timeout=12,
        )
        response.raise_for_status.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
