import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk
from langgraph.errors import GraphRecursionError
from openai import RateLimitError
from main import app


class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("service", data)
        self.assertIn("agent_configured", data)
        self.assertIn("llm_provider", data)

    def test_chat_invalid_payload(self):
        response = self.client.post("/api/chat", json={})
        self.assertEqual(response.status_code, 422)

    @patch("main.is_agent_configured", return_value=False)
    def test_chat_unconfigured_agent_notice(self, mock_is_configured):
        payload = {
            "prompt": {"content": "What is the price of AAPL?", "id": "msg-1", "role": "user"},
            "threadId": "thread-123",
            "responseId": "resp-123",
        }
        response = self.client.post("/api/chat", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/event-stream; charset=utf-8")
        text = response.text
        self.assertIn("AI Model Not Configured", text)

    @patch("main.is_agent_configured", return_value=True)
    def test_chat_streaming_success(self, mock_is_configured):
        async def mock_astream(*args, **kwargs):
            yield AIMessageChunk(content="The price is "), None
            yield AIMessageChunk(content="$350.00"), None

        with patch("main.agent.astream", side_effect=mock_astream):
            payload = {
                "prompt": {"content": "What is the price of AAPL?", "id": "msg-1", "role": "user"},
                "threadId": "thread-123",
                "responseId": "resp-123",
            }
            response = self.client.post("/api/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"], "text/event-stream; charset=utf-8")
            self.assertEqual(response.text, "<custommarkdown>The price is $350.00</custommarkdown>")

    @patch("main.is_agent_configured", return_value=True)
    def test_chat_streaming_custommarkdown_framing(self, mock_is_configured):
        async def mock_astream(*args, **kwargs):
            yield AIMessageChunk(content="Sample response chunk"), None

        with patch("main.agent.astream", side_effect=mock_astream):
            payload = {
                "prompt": {"content": "Test framing", "id": "msg-1", "role": "user"},
                "threadId": "thread-123",
            }
            response = self.client.post("/api/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.text.startswith("<custommarkdown>"))
            self.assertTrue(response.text.endswith("</custommarkdown>"))

    @patch("main.is_agent_configured", return_value=True)
    def test_chat_streaming_multiple_chunks(self, mock_is_configured):
        chunks = ["Chunk 1: Overview. ", "Chunk 2: Metrics. ", "Chunk 3: Conclusion."]

        async def mock_astream(*args, **kwargs):
            for c in chunks:
                yield AIMessageChunk(content=c), None

        with patch("main.agent.astream", side_effect=mock_astream):
            payload = {
                "prompt": {"content": "Multi chunk test", "id": "msg-1", "role": "user"},
                "threadId": "thread-123",
            }
            response = self.client.post("/api/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            expected = f"<custommarkdown>{''.join(chunks)}</custommarkdown>"
            self.assertEqual(response.text, expected)

    @patch("main.is_agent_configured", return_value=True)
    def test_chat_streaming_error_framing(self, mock_is_configured):
        async def mock_astream_err(*args, **kwargs):
            raise Exception("404: The model does not exist")
            yield  # pragma: no cover

        with patch("main.agent.astream", side_effect=mock_astream_err):
            payload = {
                "prompt": {"content": "Error framing test", "id": "msg-1", "role": "user"},
                "threadId": "thread-123",
            }
            response = self.client.post("/api/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.text.startswith("<custommarkdown>"))
            self.assertTrue(response.text.endswith("</custommarkdown>"))
            self.assertIn("Model Error (404)", response.text)

    @patch("main.is_agent_configured", return_value=True)
    def test_chat_streaming_interrupted_error_after_chunks(self, mock_is_configured):
        async def mock_astream_partial(*args, **kwargs):
            yield AIMessageChunk(content="Partial analysis completed. "), None
            raise Exception("Internal connection dropped")

        with patch("main.agent.astream", side_effect=mock_astream_partial):
            payload = {
                "prompt": {"content": "Interrupted stream test", "id": "msg-1", "role": "user"},
                "threadId": "thread-123",
            }
            response = self.client.post("/api/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.text.startswith("<custommarkdown>"))
            self.assertTrue(response.text.endswith("</custommarkdown>"))
            self.assertIn("Partial analysis completed. ", response.text)
            self.assertIn("Internal connection dropped", response.text)
            # Ensure <custommarkdown> is not duplicated
            self.assertEqual(response.text.count("<custommarkdown>"), 1)
            self.assertEqual(response.text.count("</custommarkdown>"), 1)

    @patch("main.is_agent_configured", return_value=True)
    def test_chat_streaming_headers(self, mock_is_configured):
        async def mock_astream(*args, **kwargs):
            yield AIMessageChunk(content="Header check"), None

        with patch("main.agent.astream", side_effect=mock_astream):
            payload = {
                "prompt": {"content": "Header check", "id": "msg-1", "role": "user"},
                "threadId": "thread-123",
            }
            response = self.client.post("/api/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-cache, no-transform")
            self.assertEqual(response.headers["x-accel-buffering"], "no")
            self.assertIn("text/event-stream", response.headers["content-type"])

    @patch("main.is_agent_configured", return_value=True)
    def test_chat_provider_error_handling(self, mock_is_configured):
        async def mock_astream_err(*args, **kwargs):
            raise Exception("404: The model does not exist")
            yield  # pragma: no cover

        with patch("main.agent.astream", side_effect=mock_astream_err):
            payload = {
                "prompt": {"content": "Hello", "id": "msg-1", "role": "user"},
                "threadId": "thread-123",
            }
            response = self.client.post("/api/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertIn("Model Error (404)", response.text)

    @patch("main.is_agent_configured", return_value=True)
    def test_chat_recursion_limit_handling(self, mock_is_configured):
        async def mock_astream_rec(*args, **kwargs):
            raise GraphRecursionError("Recursion limit of 8 reached")
            yield  # pragma: no cover

        with patch("main.agent.astream", side_effect=mock_astream_rec):
            payload = {
                "prompt": {"content": "Loop query", "id": "msg-1", "role": "user"},
                "threadId": "thread-123",
            }
            response = self.client.post("/api/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertIn("Analysis Limit Reached", response.text)

    @patch("main.is_agent_configured", return_value=True)
    def test_chat_empty_response_fallback(self, mock_is_configured):
        async def mock_astream_empty(*args, **kwargs):
            # No AI chunks emitted
            if False:
                yield None

        with patch("main.agent.astream", side_effect=mock_astream_empty):
            payload = {
                "prompt": {"content": "Empty output test", "id": "msg-1", "role": "user"},
                "threadId": "thread-123",
            }
            response = self.client.post("/api/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertIn("requested data has been processed", response.text)

    @patch("main.is_agent_configured", return_value=True)
    def test_chat_ratelimit_token_limit_confirmed(self, mock_is_configured):
        mock_resp = MagicMock()
        mock_resp.headers = {"retry-after": "15", "x-request-id": "req_tok_123"}
        mock_resp.status_code = 429
        mock_err = RateLimitError(
            message="Rate limit reached for model openai/gpt-oss-120b on tokens per minute (TPM).",
            response=mock_resp,
            body={"error": {"message": "Rate limit on tokens per minute (TPM)"}},
        )

        async def mock_astream_rate_limit(*args, **kwargs):
            raise mock_err
            yield  # pragma: no cover

        with patch("main.agent.astream", side_effect=mock_astream_rate_limit):
            payload = {
                "prompt": {"content": "Trigger TPM limit", "id": "msg-1", "role": "user"},
                "threadId": "thread-123",
            }
            response = self.client.post("/api/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertIn("token quota (TPM)", response.text)
            self.assertIn("15 seconds", response.text)
            self.assertIn("req_tok_123", response.text)

    @patch("main.is_agent_configured", return_value=True)
    def test_chat_ratelimit_request_limit_confirmed(self, mock_is_configured):
        mock_resp = MagicMock()
        mock_resp.headers = {"retry-after": "45", "x-request-id": "req_rpd_456"}
        mock_resp.status_code = 429
        mock_err = RateLimitError(
            message="Rate limit reached on requests per day (RPD): Limit 1000.",
            response=mock_resp,
            body={"error": {"message": "Rate limit on requests per day (RPD)"}},
        )

        async def mock_astream_rate_limit(*args, **kwargs):
            raise mock_err
            yield  # pragma: no cover

        with patch("main.agent.astream", side_effect=mock_astream_rate_limit):
            payload = {
                "prompt": {"content": "Trigger RPD limit", "id": "msg-1", "role": "user"},
                "threadId": "thread-123",
            }
            response = self.client.post("/api/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertIn("daily request quota (RPD)", response.text)
            self.assertIn("45 seconds", response.text)
            self.assertIn("req_rpd_456", response.text)

    @patch("main.is_agent_configured", return_value=True)
    def test_chat_ratelimit_neutral_fallback_when_unspecified(self, mock_is_configured):
        mock_resp = MagicMock()
        mock_resp.headers = {"retry-after": "5", "x-request-id": "req_gen_789"}
        mock_resp.status_code = 429
        mock_err = RateLimitError(
            message="Too many requests. Please slow down.",
            response=mock_resp,
            body={"error": {"message": "Too many requests"}},
        )

        async def mock_astream_rate_limit(*args, **kwargs):
            raise mock_err
            yield  # pragma: no cover

        with patch("main.agent.astream", side_effect=mock_astream_rate_limit):
            payload = {
                "prompt": {"content": "Trigger generic 429", "id": "msg-1", "role": "user"},
                "threadId": "thread-123",
            }
            response = self.client.post("/api/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertIn("Provider rate limit reached.", response.text)
            self.assertNotIn("token quota", response.text)
            self.assertIn("5 seconds", response.text)

    @patch("main.is_agent_configured", return_value=True)
    def test_chat_ratelimit_missing_retry_after(self, mock_is_configured):
        mock_resp = MagicMock()
        mock_resp.headers = {"x-request-id": "req_no_retry"}  # No retry-after
        mock_resp.status_code = 429
        mock_err = RateLimitError(
            message="Rate limit reached without retry header",
            response=mock_resp,
            body={"error": {"message": "Rate limit reached"}},
        )

        async def mock_astream_rate_limit(*args, **kwargs):
            raise mock_err
            yield  # pragma: no cover

        with patch("main.agent.astream", side_effect=mock_astream_rate_limit):
            payload = {
                "prompt": {"content": "Trigger 429 no retry-after", "id": "msg-1", "role": "user"},
                "threadId": "thread-123",
            }
            response = self.client.post("/api/chat", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertIn("Please wait a few moments before trying again.", response.text)
            self.assertNotIn("None seconds", response.text)

    @patch("main.is_agent_configured", return_value=True)
    def test_chat_ratelimit_sanitized_logs(self, mock_is_configured):
        mock_resp = MagicMock()
        mock_resp.headers = {"retry-after": "10", "x-request-id": "req_sanitized_999"}
        mock_resp.status_code = 429
        mock_err = RateLimitError(
            message="Rate limit on tokens per minute",
            response=mock_resp,
            body={"error": {"message": "Rate limit on tokens per minute"}},
        )

        async def mock_astream_rate_limit(*args, **kwargs):
            raise mock_err
            yield  # pragma: no cover

        with patch("main.agent.astream", side_effect=mock_astream_rate_limit):
            payload = {
                "prompt": {"content": "Test log sanitization", "id": "msg-1", "role": "user"},
                "threadId": "thread-123",
            }
            with self.assertLogs("main", level="WARNING") as captured_logs:
                response = self.client.post("/api/chat", json=payload)
                self.assertEqual(response.status_code, 200)

            logged_text = " ".join(captured_logs.output)
            self.assertIn("req_sanitized_999", logged_text)
            self.assertIn("token quota (TPM)", logged_text)
            self.assertNotIn("gsk_", logged_text)
            self.assertNotIn("Bearer", logged_text)
            self.assertNotIn("Authorization", logged_text)

    def test_cors_headers(self):
        headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        }
        response = self.client.options("/api/chat", headers=headers)
        self.assertIn("access-control-allow-origin", response.headers)


if __name__ == "__main__":
    unittest.main()
