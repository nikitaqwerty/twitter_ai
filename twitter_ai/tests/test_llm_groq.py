# twitter_ai/tests/test_llm_groq.py

import unittest
from unittest.mock import patch, MagicMock
from llm.llm_groq import GroqLLM


class TestGroqLLM(unittest.TestCase):

    @patch("llm.llm_groq.Groq")
    def test_get_response_success(self, MockGroq):
        mock_client = MockGroq.return_value
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Test response"))
        ]
        mock_client.chat.completions.create.return_value = mock_completion

        groq_llm = GroqLLM(api_key="fake_api_key")
        response = groq_llm.get_response("Test query")

        self.assertEqual(response, "Test response")

    @patch("llm.llm_groq.Groq")
    def test_get_response_failure(self, MockGroq):
        mock_client = MockGroq.return_value
        mock_client.chat.completions.create.side_effect = Exception("Test exception")

        groq_llm = GroqLLM(api_key="fake_api_key")
        response = groq_llm.get_response("Test query")

        self.assertIsNone(response)


if __name__ == "__main__":
    unittest.main()
