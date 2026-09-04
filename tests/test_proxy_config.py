import unittest

from service.proxy_config import (
    build_playwright_proxy,
    build_proxy_url,
    mask_proxy_url,
    normalize_proxy_server,
)


class ProxyConfigTests(unittest.TestCase):
    def test_normalize_blank_bare_and_supported_servers(self):
        cases = (
            ("", "http", ""),
            (" proxy.test:8080 ", "http", "http://proxy.test:8080"),
            ("proxy.test:8443", "HTTPS", "https://proxy.test:8443"),
            ("proxy.test:1080", "socks5", "socks5://proxy.test:1080"),
            ("http://proxy.test:80", "socks5", "http://proxy.test:80"),
        )
        for server, proxy_type, expected in cases:
            with self.subTest(server=server, proxy_type=proxy_type):
                self.assertEqual(normalize_proxy_server(server, proxy_type), expected)

    def test_normalize_rejects_current_invalid_server_shapes(self):
        cases = (
            ("ftp://proxy.test", "Unsupported proxy type."),
            (
                "http://user:secret@proxy.test",
                "Proxy credentials must be stored in username/password fields, not in server.",
            ),
            ("http://", "Proxy server must include a host."),
            ("http://proxy.test/path", "Proxy server must not include path, query, or fragment."),
            ("http://proxy.test?query=1", "Proxy server must not include path, query, or fragment."),
            ("http://proxy.test#fragment", "Proxy server must not include path, query, or fragment."),
        )
        for server, message in cases:
            with self.subTest(server=server):
                with self.assertRaises(ValueError) as raised:
                    normalize_proxy_server(server)
                self.assertEqual(str(raised.exception), message)

    def test_builders_quote_credentials_and_preserve_current_mapping(self):
        profile = {
            "server": "proxy.test:8080",
            "proxy_type": "https",
            "username": "user@example.test",
            "password": "p:/ word",
        }
        self.assertEqual(
            build_proxy_url(profile),
            "https://user%40example.test:p%3A%2F%20word@proxy.test:8080",
        )
        self.assertEqual(
            build_playwright_proxy(profile),
            {
                "server": "https://proxy.test:8080",
                "username": "user@example.test",
                "password": "p:/ word",
            },
        )

        password_only = {"server": "proxy.test:8080", "password": "secret"}
        self.assertEqual(build_proxy_url(password_only), "http://proxy.test:8080")
        self.assertEqual(
            build_playwright_proxy(password_only),
            {"server": "http://proxy.test:8080", "password": "secret"},
        )

    def test_masking_removes_profile_and_embedded_secrets(self):
        profile = {
            "server": "proxy.test:8080",
            "username": "visible-user",
            "password": "profile-secret",
        }
        masked = mask_proxy_url(profile)
        self.assertEqual(masked, "http://visible-user:***@proxy.test:8080")
        self.assertNotIn("profile-secret", masked)

        embedded = mask_proxy_url(
            {"server": "http://embedded-user:embedded-secret@proxy.test:8080"}
        )
        self.assertEqual(embedded, "http://***:***@proxy.test:8080")
        self.assertNotIn("embedded-user", embedded)
        self.assertNotIn("embedded-secret", embedded)
        self.assertEqual(mask_proxy_url(None), "")


if __name__ == "__main__":
    unittest.main()
