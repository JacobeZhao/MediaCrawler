import unittest

import httpx

from service.providers.justoneapi.client import JustOneApiClient, redact_token
from service.providers.justoneapi.errors import (
    JustOneApiCredentialError,
    JustOneApiUnknownOutcomeError,
)


def envelope(code=0, message="ok", data=None, request_id="request-1"):
    return {
        "code": code,
        "message": message,
        "data": {} if data is None else data,
        "recordTime": "2026-07-14T12:00:00+08:00",
        "requestId": request_id,
    }


class JustOneApiClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_search_uses_https_endpoint_and_token_query(self):
        seen = []

        async def handler(request):
            seen.append(request)
            return httpx.Response(
                200,
                json=envelope(data={"items": [{"id": "note-1"}]}),
            )

        client = JustOneApiClient(
            "top-secret-token",
            transport=httpx.MockTransport(handler),
            retry_base_sec=0,
        )
        self.addAsyncCleanup(client.aclose)

        result = await client.search_notes(
            "coffee",
            page=2,
            sort_type="time_descending",
            note_type="NORMAL_NOTE",
            time_filter="ONE_WEEK",
            search_id="search-1",
            session_id="session-1",
        )

        self.assertEqual(result.code, 0)
        self.assertEqual(result.data["items"][0]["id"], "note-1")
        self.assertEqual(len(seen), 1)
        request = seen[0]
        self.assertEqual(request.url.scheme, "https")
        self.assertEqual(request.url.path, "/api/xiaohongshu/search-note/v4")
        self.assertEqual(request.url.params["token"], "top-secret-token")
        self.assertEqual(request.url.params["keyword"], "coffee")
        self.assertEqual(request.url.params["searchId"], "search-1")
        self.assertEqual(request.url.params["sessionId"], "session-1")

    async def test_search_transport_defaults_are_stable(self):
        requests = []

        async def handler(request):
            requests.append(request)
            return httpx.Response(200, json=envelope())

        client = JustOneApiClient(
            "token",
            transport=httpx.MockTransport(handler),
            retry_base_sec=0,
        )
        self.addAsyncCleanup(client.aclose)

        await client.search_notes("coffee")

        params = requests[0].url.params
        self.assertEqual(params["sortType"], "general")
        self.assertEqual(params["noteType"], "ALL")
        self.assertEqual(params["timeFilter"], "ALL")

    async def test_public_endpoint_contract_maps_expected_parameters(self):
        requests = []

        async def handler(request):
            requests.append(request)
            return httpx.Response(200, json=envelope())

        client = JustOneApiClient(
            "token",
            transport=httpx.MockTransport(handler),
            retry_base_sec=0,
        )
        self.addAsyncCleanup(client.aclose)

        await client.creator_notes("user-1", cursor="cursor-1", xsec_token="xsec")
        await client.user_profile("user-1", xsec_token="xsec")
        await client.note_detail("note-1", xsec_token="xsec")
        await client.comments("note-1", cursor="cursor-2", xsec_token="xsec")
        await client.replies(
            "note-1",
            "comment-1",
            cursor="cursor-3",
            xsec_token="xsec",
        )
        await client.resolve_share_link("https://xhslink.com/example")

        self.assertEqual(
            [request.url.path for request in requests],
            [
                "/api/xiaohongshu/get-user-note-list/v4",
                "/api/xiaohongshu/get-user/v4",
                "/api/xiaohongshu/get-note-detail/v4",
                "/api/xiaohongshu/get-note-comment/v4",
                "/api/xiaohongshu/get-note-sub-comment/v2",
                "/api/xiaohongshu/share-url-transfer/v1",
            ],
        )
        self.assertEqual(requests[0].url.params["lastCursor"], "cursor-1")
        self.assertNotIn("xsecToken", requests[0].url.params)
        self.assertNotIn("xsecToken", requests[1].url.params)
        self.assertNotIn("xsecToken", requests[2].url.params)
        self.assertEqual(requests[3].url.params["lastCursor"], "cursor-2")
        self.assertEqual(requests[4].url.params["commentId"], "comment-1")
        self.assertEqual(
            requests[5].url.params["shareUrl"],
            "https://xhslink.com/example",
        )

    async def test_business_failure_is_returned_and_observed_before_policy(self):
        records = []

        async def handler(request):
            return httpx.Response(
                429,
                json=envelope(code=302, message="rate limited", request_id="req-302"),
            )

        client = JustOneApiClient(
            "token",
            transport=httpx.MockTransport(handler),
        )
        self.addAsyncCleanup(client.aclose)

        result = await client.search_notes("coffee", observer=records.append)

        self.assertEqual(result.code, 302)
        self.assertEqual(result.http_status, 429)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].business_code, 302)
        self.assertFalse(records[0].billed)

    async def test_connect_failure_retries_with_exponential_delay(self):
        calls = 0
        delays = []

        async def handler(request):
            nonlocal calls
            calls += 1
            if calls < 3:
                raise httpx.ConnectError(
                    "failed https://example.test?token=top-secret-token",
                    request=request,
                )
            return httpx.Response(200, json=envelope())

        async def fake_sleep(seconds):
            delays.append(seconds)

        client = JustOneApiClient(
            "top-secret-token",
            max_retries=2,
            retry_base_sec=0.5,
            transport=httpx.MockTransport(handler),
            sleep=fake_sleep,
        )
        self.addAsyncCleanup(client.aclose)

        result = await client.search_notes("coffee")

        self.assertEqual(result.code, 0)
        self.assertEqual(calls, 3)
        self.assertEqual(delays, [0.5, 1.0])

    async def test_read_timeout_is_not_retried_and_does_not_expose_token(self):
        calls = 0

        async def handler(request):
            nonlocal calls
            calls += 1
            raise httpx.ReadTimeout(
                "https://example.test?token=top-secret-token",
                request=request,
            )

        client = JustOneApiClient(
            "top-secret-token",
            max_retries=5,
            retry_base_sec=0,
            transport=httpx.MockTransport(handler),
        )
        self.addAsyncCleanup(client.aclose)

        with self.assertRaises(JustOneApiUnknownOutcomeError) as caught:
            await client.search_notes("coffee")

        self.assertEqual(calls, 1)
        self.assertNotIn("top-secret-token", str(caught.exception))
        self.assertNotIn("?token=", str(caught.exception))

    async def test_post_connect_http_error_is_unknown_and_not_retried(self):
        calls = 0
        records = []

        async def handler(request):
            nonlocal calls
            calls += 1
            raise httpx.ReadError("connection reset", request=request)

        client = JustOneApiClient(
            "token",
            max_retries=5,
            retry_base_sec=0,
            transport=httpx.MockTransport(handler),
        )
        self.addAsyncCleanup(client.aclose)

        with self.assertRaises(JustOneApiUnknownOutcomeError):
            await client.search_notes("coffee", observer=records.append)

        self.assertEqual(calls, 1)
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0].outcome_unknown)

    async def test_provider_message_is_redacted_without_losing_envelope(self):
        async def handler(request):
            return httpx.Response(
                401,
                json=envelope(
                    code=100,
                    message="bad token top-secret-token and ?token=another-secret",
                ),
            )

        client = JustOneApiClient(
            "top-secret-token",
            transport=httpx.MockTransport(handler),
        )
        self.addAsyncCleanup(client.aclose)

        result = await client.search_notes("coffee")

        self.assertEqual(result.code, 100)
        self.assertNotIn("top-secret-token", result.message)
        self.assertNotIn("another-secret", result.message)
        self.assertIn("[REDACTED]", result.message)

    async def test_missing_token_fails_without_network_request(self):
        calls = 0

        async def handler(request):
            nonlocal calls
            calls += 1
            return httpx.Response(200, json=envelope())

        client = JustOneApiClient("", transport=httpx.MockTransport(handler))
        self.addAsyncCleanup(client.aclose)

        with self.assertRaises(JustOneApiCredentialError):
            await client.search_notes("coffee")
        self.assertEqual(calls, 0)

    async def test_aclose_is_idempotent(self):
        client = JustOneApiClient(
            "token",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=envelope())
            ),
        )
        await client.aclose()
        await client.aclose()
        self.assertTrue(client.closed)

    def test_rejects_insecure_base_url_and_redacts_query_strings(self):
        with self.assertRaises(ValueError):
            JustOneApiClient("token", base_url="http://api.justoneapi.com")
        self.assertEqual(
            redact_token("GET /path?token=secret&next=1"),
            "GET /path?token=[REDACTED]&next=1",
        )


if __name__ == "__main__":
    unittest.main()
