import unittest
from unittest.mock import patch
from StockPrism.components.agent import (
    is_agent_configured,
    build_agent,
    ALL_TOOLS,
    get_effective_llm_config,
    DEFAULT_GROQ_MODEL,
)


class TestAgent(unittest.TestCase):
    def test_tools_count(self):
        # 16 tools configured
        self.assertEqual(len(ALL_TOOLS), 16)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "", "GROQ_API_KEY": "", "GEMINI_API_KEY": ""}, clear=True)
    def test_is_agent_configured_empty(self):
        self.assertFalse(is_agent_configured())

    @patch.dict("os.environ", {"OPENAI_API_KEY": "your_api_key_here", "GROQ_API_KEY": "", "GEMINI_API_KEY": ""}, clear=True)
    def test_is_agent_configured_placeholder(self):
        self.assertFalse(is_agent_configured())

    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-real-valid-api-key", "GROQ_API_KEY": "", "GEMINI_API_KEY": ""}, clear=True)
    def test_is_agent_configured_openai_valid(self):
        self.assertTrue(is_agent_configured())
        config = get_effective_llm_config()
        self.assertEqual(config["provider"], "OpenAI / Custom")

    @patch.dict("os.environ", {"GROQ_API_KEY": "gsk_test123", "OPENAI_API_KEY": "", "GEMINI_API_KEY": ""}, clear=True)
    def test_is_agent_configured_groq(self):
        self.assertTrue(is_agent_configured())
        config = get_effective_llm_config()
        self.assertEqual(config["provider"], "Groq")
        self.assertEqual(config["model"], DEFAULT_GROQ_MODEL)
        self.assertEqual(config["base_url"], "https://api.groq.com/openai/v1")

    @patch.dict("os.environ", {"GROQ_API_KEY": "gsk_test123", "GROQ_MODEL": "openai/gpt-oss-20b"}, clear=True)
    def test_is_agent_configured_groq_custom_model(self):
        self.assertTrue(is_agent_configured())
        config = get_effective_llm_config()
        self.assertEqual(config["provider"], "Groq")
        self.assertEqual(config["model"], "openai/gpt-oss-20b")

    @patch.dict("os.environ", {"GEMINI_API_KEY": "AIzaSy_test123", "OPENAI_API_KEY": "", "GROQ_API_KEY": ""}, clear=True)
    def test_is_agent_configured_gemini(self):
        self.assertTrue(is_agent_configured())
        config = get_effective_llm_config()
        self.assertEqual(config["provider"], "Google AI Studio")
        self.assertEqual(config["model"], "gemini-2.0-flash")

    @patch.dict("os.environ", {"OPENAI_API_KEY": "gsk_pasted_into_openai_field", "GROQ_API_KEY": "", "GEMINI_API_KEY": ""}, clear=True)
    def test_is_agent_configured_groq_autodetect(self):
        self.assertTrue(is_agent_configured())
        config = get_effective_llm_config()
        self.assertEqual(config["provider"], "Groq (Auto-detected)")
        self.assertEqual(config["base_url"], "https://api.groq.com/openai/v1")
        self.assertEqual(config["model"], DEFAULT_GROQ_MODEL)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "", "GROQ_API_KEY": "", "GEMINI_API_KEY": ""}, clear=True)
    def test_build_agent_unconfigured(self):
        # Should build in standby mode without raising OpenAIError
        agent_instance = build_agent()
        self.assertIsNotNone(agent_instance)
        self.assertTrue(hasattr(agent_instance, "astream"))


if __name__ == "__main__":
    unittest.main()
