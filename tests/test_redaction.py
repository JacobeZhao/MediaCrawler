import unittest
from unittest.mock import AsyncMock, patch

from media_platform.xhs.client import XiaoHongShuClient
from service.circuit_breaker import CrawlCircuitBreaker
from service.task_manager import TaskManager
from tools.crawler_util import find_login_qrcode
from tools.redaction import redact_sensitive_text


class RedactionTests(unittest.TestCase):
    def test_redacts_sensitive_query_and_json_values(self):
        value = (
            "https://example.test/note?xsec_token=secret-token&xsec_source=search "
            '{"password":"secret-password","cookie_json":"secret-cookie"}'
        )

        result = redact_sensitive_text(value)

        self.assertNotIn("secret-token", result)
        self.assertNotIn("secret-password", result)
        self.assertNotIn("secret-cookie", result)
        self.assertIn("xsec_token=<redacted>", result)

    def test_bounds_diagnostic_text(self):
        result = redact_sensitive_text("x" * 20, max_length=5)

        self.assertEqual(result, "xxxxx...<truncated>")

    def test_redacts_headers_and_url_userinfo(self):
        value = (
            "Authorization: Bearer bearer-secret\n"
            "Cookie: arbitrary_name=cookie-secret\n"
            "proxy=http://user:proxy-secret@example.test:8080"
        )

        result = redact_sensitive_text(value)

        self.assertNotIn("bearer-secret", result)
        self.assertNotIn("cookie-secret", result)
        self.assertNotIn("proxy-secret", result)

    def test_remote_error_redacts_every_error_subclass(self):
        client = object.__new__(XiaoHongShuClient)
        client.IP_ERROR_CODE = 300012
        for status_code in (401, 403, 429, 471, 500):
            error = client._build_remote_error(
                "request failed xsec_token=message-secret",
                status_code=status_code,
                response_text="cookie_json=response-secret",
            )
            self.assertNotIn("message-secret", str(error))
            self.assertNotIn("response-secret", error.response_text)


class PersistenceRedactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_pause_and_risk_event_redact_at_persistence_boundary(self):
        manager = object.__new__(TaskManager)
        manager._lease_owner = "owner"
        update = AsyncMock(return_value=True)
        with patch("service.task_manager.db.update_task_status_if_owned", new=update):
            await manager._pause_owned_task(
                1,
                "paused xsec_token=message-secret",
                error="cookie_json=error-secret",
            )

        update_kwargs = update.await_args.kwargs
        self.assertNotIn("message-secret", update_kwargs["progress"])
        self.assertNotIn("error-secret", update_kwargs["error"])

        breaker = CrawlCircuitBreaker()
        add_event = AsyncMock()
        with (
            patch("service.circuit_breaker.db.add_crawl_event", new=add_event),
            patch(
                "service.circuit_breaker.db.count_recent_crawl_events",
                new=AsyncMock(return_value=0),
            ),
        ):
            await breaker.record_risk_event(
                "account_error",
                message="password=risk-secret",
            )
        self.assertNotIn("risk-secret", add_event.await_args.kwargs["message"])

    async def test_qr_fetch_failure_never_logs_url_or_response_body(self):
        class Element:
            async def get_property(self, name):
                return "https://example.test/qr?token=url-secret"

        page = AsyncMock()
        page.wait_for_selector.return_value = Element()

        class Response:
            status_code = 500
            text = "response-secret"

        class Client:
            async def get(self, *args, **kwargs):
                return Response()

        class ClientContext:
            async def __aenter__(self):
                return Client()

            async def __aexit__(self, *args):
                return None

        with (
            patch("tools.crawler_util.make_async_client", return_value=ClientContext()),
            self.assertLogs("MediaCrawler", level="INFO") as captured,
        ):
            result = await find_login_qrcode(page, "#qr")

        logs = "\n".join(captured.output)
        self.assertEqual(result, "")
        self.assertNotIn("url-secret", logs)
        self.assertNotIn("response-secret", logs)


if __name__ == "__main__":
    unittest.main()
