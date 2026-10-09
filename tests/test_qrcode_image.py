import base64
import unittest
from unittest.mock import AsyncMock, patch

from tools.crawler_util import find_login_qrcode


class QrcodeImageTests(unittest.IsolatedAsyncioTestCase):
    async def test_remote_image_returns_browser_usable_data_uri(self):
        image_bytes = b"\x89PNG\r\n\x1a\nqr-test-image"
        handle = AsyncMock()
        handle.json_value.return_value = "https://example.test/qr.png"
        element = AsyncMock()
        element.get_property.return_value = handle
        page = AsyncMock()
        page.wait_for_selector.return_value = element

        response = AsyncMock()
        response.status_code = 200
        response.content = image_bytes
        response.headers = {"content-type": "image/png"}
        client = AsyncMock()
        client.get.return_value = response
        context = AsyncMock()
        context.__aenter__.return_value = client

        with patch("tools.crawler_util.make_async_client", return_value=context):
            result = await find_login_qrcode(page, "#qr")

        prefix, encoded = result.split(",", 1)
        self.assertEqual(prefix, "data:image/png;base64")
        self.assertEqual(base64.b64decode(encoded), image_bytes)
        client.get.assert_awaited_once()
        self.assertEqual(client.get.await_args.args[0], "https://example.test/qr.png")

    async def test_existing_data_uri_is_preserved(self):
        uri = "data:image/png;base64," + base64.b64encode(b"image").decode()
        handle = AsyncMock()
        handle.json_value.return_value = uri
        element = AsyncMock()
        element.get_property.return_value = handle
        page = AsyncMock()
        page.wait_for_selector.return_value = element

        self.assertEqual(await find_login_qrcode(page, "#qr"), uri)
