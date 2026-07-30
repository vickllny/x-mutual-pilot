import json
import unittest

from x_mutual_pilot.drafts import LocalDraftGenerator, OpenAIDraftGenerator


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._body = json.dumps(payload).encode()

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class DraftGeneratorTests(unittest.TestCase):
    def test_local_generator_matches_detected_language(self) -> None:
        generator = LocalDraftGenerator()

        chinese = generator.generate("这是一个很有意思的产品观察。")
        english = generator.generate("A thoughtful product observation.")

        self.assertIn("感谢", chinese["draft"])
        self.assertIn("Thanks", english["draft"])
        self.assertNotIn("ai_generated", chinese["risk_flags"])

    def test_openai_generator_uses_responses_and_collects_output_text(self) -> None:
        captured = {}

        def opener(request: object, *, timeout: float) -> FakeResponse:
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data)
            return FakeResponse(
                {
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": "Thoughtful point."}
                            ],
                        }
                    ]
                }
            )

        result = OpenAIDraftGenerator(
            "openai-secret", model="gpt-5.6-luna", opener=opener
        ).generate("Original post")

        self.assertEqual(result["draft"], "Thoughtful point.")
        self.assertIn("ai_generated", result["risk_flags"])
        self.assertEqual(captured["url"], "https://api.openai.com/v1/responses")
        self.assertEqual(captured["body"]["store"], False)
        self.assertNotIn("openai-secret", str(result))


if __name__ == "__main__":
    unittest.main()
