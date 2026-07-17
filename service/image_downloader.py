import asyncio
import os
import tempfile
import urllib.parse
import urllib.request
from typing import Any, Iterable, Optional


_SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _normalize_url(url: str) -> str:
    url = str(url or "").strip().strip('"').strip("'")
    if url.startswith("http://"):
        return "https://" + url[7:]
    return url


def _image_urls(raw_images: Any) -> list[str]:
    if not raw_images:
        return []
    if isinstance(raw_images, str):
        items: Iterable[Any] = raw_images.split(",")
    elif isinstance(raw_images, Iterable):
        items = raw_images
    else:
        return []

    urls: list[str] = []
    for item in items:
        if isinstance(item, dict):
            url = item.get("url") or item.get("url_default") or item.get("url_pre") or item.get("url_default")
        else:
            url = item
        url = _normalize_url(str(url or ""))
        if url.startswith("http"):
            urls.append(url)
    return urls


def _extension_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    return ext if ext in _SUPPORTED_EXTENSIONS else ".jpg"


def _existing_image_path(note_dir: str, index: int) -> Optional[str]:
    for ext in _SUPPORTED_EXTENSIONS:
        path = os.path.join(note_dir, f"{index}{ext}")
        if os.path.exists(path):
            return path
    return None


def _download_image(url: str, note_dir: str, index: int, timeout: int = 12) -> Optional[str]:
    os.makedirs(note_dir, exist_ok=True)
    existing = _existing_image_path(note_dir, index)
    if existing:
        return existing

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.xiaohongshu.com/",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()

    if not raw:
        return None

    ext = _CONTENT_TYPE_EXTENSIONS.get(content_type) or _extension_from_url(url)
    final_path = os.path.join(note_dir, f"{index}{ext}")
    fd, tmp_path = tempfile.mkstemp(prefix=f"{index}.", suffix=".tmp", dir=note_dir)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(raw)
        os.replace(tmp_path, final_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    return final_path


async def download_note_images(note_id: str, raw_images: Any, image_dir: str, limit: int = 10) -> list[str]:
    if not note_id:
        return []
    urls = _image_urls(raw_images)[:limit]
    if not urls:
        return []
    note_dir = os.path.join(image_dir, note_id)
    results: list[str] = []
    for index, url in enumerate(urls):
        try:
            path = await asyncio.to_thread(_download_image, url, note_dir, index)
        except Exception:
            path = None
        if path:
            results.append(path)
    return results
