import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from service import image_downloader


class _Response:
    def __init__(self, body: bytes, content_type: str = ""):
        self._body = body
        self.headers = {"content-type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return self._body


class ImageDownloaderTests(unittest.IsolatedAsyncioTestCase):
    def test_image_urls_normalize_supported_input_shapes_in_order(self):
        raw_images = [
            " http://images.test/one.png ",
            {"url_default": "'https://images.test/two.webp'"},
            {"url_pre": '"https://images.test/three.jpg"'},
            {"url": "ftp://images.test/ignored.jpg"},
            None,
        ]

        self.assertEqual(
            image_downloader._image_urls(raw_images),
            [
                "https://images.test/one.png",
                "https://images.test/two.webp",
                "https://images.test/three.jpg",
            ],
        )
        self.assertEqual(
            image_downloader._image_urls(
                "http://images.test/a.jpg, https://images.test/b.jpeg"
            ),
            ["https://images.test/a.jpg", "https://images.test/b.jpeg"],
        )
        self.assertEqual(image_downloader._image_urls(123), [])

    def test_existing_cached_image_skips_the_request(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            note_dir = Path(temporary_directory) / "note"
            note_dir.mkdir()
            cached = note_dir / "2.webp"
            cached.write_bytes(b"cached")

            with patch(
                "service.image_downloader.urllib.request.urlopen",
                side_effect=AssertionError("cache hit must not fetch"),
            ) as urlopen:
                result = image_downloader._download_image(
                    "https://images.test/new.jpg", str(note_dir), 2
                )

            self.assertEqual(result, str(cached))
            urlopen.assert_not_called()

    def test_download_uses_headers_timeout_type_and_atomic_replace(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            note_dir = Path(temporary_directory) / "note"
            body = b"png payload"
            real_replace = os.replace
            with (
                patch(
                    "service.image_downloader.urllib.request.urlopen",
                    return_value=_Response(body, "image/png; charset=binary"),
                ) as urlopen,
                patch(
                    "service.image_downloader.os.replace", wraps=real_replace
                ) as replace,
            ):
                result = image_downloader._download_image(
                    "https://images.test/photo.unknown", str(note_dir), 4, timeout=7
                )

            final_path = note_dir / "4.png"
            self.assertEqual(result, str(final_path))
            self.assertEqual(final_path.read_bytes(), body)
            self.assertEqual(list(note_dir.glob("*.tmp")), [])
            request = urlopen.call_args.args[0]
            self.assertEqual(request.full_url, "https://images.test/photo.unknown")
            self.assertIn("Mozilla/5.0", request.get_header("User-agent"))
            self.assertEqual(
                request.get_header("Referer"), "https://www.xiaohongshu.com/"
            )
            self.assertEqual(urlopen.call_args.kwargs, {"timeout": 7})
            self.assertEqual(replace.call_count, 1)
            self.assertEqual(Path(replace.call_args.args[1]), final_path)

    def test_empty_body_and_replace_failure_leave_no_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            note_dir = Path(temporary_directory) / "empty"
            with patch(
                "service.image_downloader.urllib.request.urlopen",
                return_value=_Response(b"", "image/jpeg"),
            ):
                result = image_downloader._download_image(
                    "https://images.test/empty.jpg", str(note_dir), 0
                )
            self.assertIsNone(result)
            self.assertEqual(list(note_dir.iterdir()), [])

        with tempfile.TemporaryDirectory() as temporary_directory:
            note_dir = Path(temporary_directory) / "failure"
            with (
                patch(
                    "service.image_downloader.urllib.request.urlopen",
                    return_value=_Response(b"payload", "image/jpeg"),
                ),
                patch(
                    "service.image_downloader.os.replace",
                    side_effect=OSError("replace failed"),
                ),
            ):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    image_downloader._download_image(
                        "https://images.test/failure.jpg", str(note_dir), 1
                    )
            self.assertEqual(list(note_dir.iterdir()), [])

    async def test_async_download_limits_order_and_isolates_failures(self):
        calls = []

        def download(url, note_dir, index):
            calls.append((url, note_dir, index))
            if index == 1:
                raise OSError("isolated failure")
            return f"result-{index}"

        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch("service.image_downloader._download_image", side_effect=download):
                self.assertEqual(
                    await image_downloader.download_note_images(
                        "note-id",
                        [
                            "https://images.test/0.jpg",
                            "https://images.test/1.jpg",
                            "https://images.test/2.jpg",
                            "https://images.test/3.jpg",
                        ],
                        temporary_directory,
                        limit=3,
                    ),
                    ["result-0", "result-2"],
                )
                self.assertEqual(
                    await image_downloader.download_note_images(
                        "", ["https://images.test/unused.jpg"], temporary_directory
                    ),
                    [],
                )

        expected_dir = str(Path(temporary_directory) / "note-id")
        self.assertEqual(
            calls,
            [
                ("https://images.test/0.jpg", expected_dir, 0),
                ("https://images.test/1.jpg", expected_dir, 1),
                ("https://images.test/2.jpg", expected_dir, 2),
            ],
        )


if __name__ == "__main__":
    unittest.main()
