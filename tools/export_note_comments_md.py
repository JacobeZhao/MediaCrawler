import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen


def fetch_json(url: str):
    with urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def format_time(value) -> str:
    try:
        timestamp = int(value) / 1000
    except (TypeError, ValueError):
        return "未知时间"
    return datetime.fromtimestamp(timestamp, timezone.utc).astimezone().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def escape_inline(value) -> str:
    text = str(value or "").replace("\\", "\\\\")
    for char in ("*", "_", "[", "]", "`"):
        text = text.replace(char, f"\\{char}")
    return text


def quote_lines(text, indent: str) -> list[str]:
    lines = str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return [f"{indent}> {line}" if line else f"{indent}>" for line in lines]


def parse_images(raw) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        parsed = raw
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [item.strip() for item in str(parsed).strip('"').split(",") if item.strip()]


def render_comment(
    comment,
    comments_by_id,
    children,
    indent: str,
    marker: str,
) -> list[str]:
    continuation = indent + (" " * len(marker))
    nickname = escape_inline(comment.get("nickname") or "未知用户")
    parent_id = str(comment.get("parent_comment_id") or "0")
    reply_target = ""
    if parent_id != "0" and parent_id in comments_by_id:
        parent_name = escape_inline(
            comments_by_id[parent_id].get("nickname") or "未知用户"
        )
        reply_target = f" 回复 **@{parent_name}**"

    metadata = [format_time(comment.get("create_time"))]
    if comment.get("ip_location"):
        metadata.append(str(comment["ip_location"]))
    metadata.append(f"赞 {comment.get('like_count') or 0}")
    metadata.append(f"ID `{comment.get('comment_id')}`")

    lines = [
        f"{indent}{marker}**{nickname}**{reply_target}  ",
        f"{continuation}{' · '.join(metadata)}",
    ]
    lines.extend(quote_lines(comment.get("content"), continuation))
    lines.append("")

    for child in children.get(str(comment.get("comment_id")), []):
        lines.extend(
            render_comment(
                child,
                comments_by_id,
                children,
                continuation,
                "- ",
            )
        )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--note-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    note_id = args.note_id
    notes = fetch_json(f"{api_base}/api/notes?keyword={note_id}&limit=10")
    note = next((item for item in notes if item.get("note_id") == note_id), None)
    if note is None:
        raise RuntimeError(f"note not found: {note_id}")
    comments = fetch_json(f"{api_base}/api/notes/{note_id}/comments?limit=10000")

    comments_by_id = {str(item["comment_id"]): item for item in comments}
    if len(comments_by_id) != len(comments):
        raise RuntimeError("duplicate comment IDs found")

    children: dict[str, list[dict]] = {}
    roots = []
    for comment in comments:
        parent_id = str(comment.get("parent_comment_id") or "0")
        if parent_id == "0":
            roots.append(comment)
        elif parent_id in comments_by_id:
            children.setdefault(parent_id, []).append(comment)
        else:
            raise RuntimeError(
                f"missing parent {parent_id} for comment {comment.get('comment_id')}"
            )

    sort_key = lambda item: (int(item.get("create_time") or 0), str(item["comment_id"]))
    roots.sort(key=sort_key)
    for items in children.values():
        items.sort(key=sort_key)

    reply_count = len(comments) - len(roots)
    lines = [
        f"# {note.get('title') or '小红书笔记评论导出'}",
        "",
        "## 笔记信息",
        "",
        f"- 作者：{note.get('nickname') or '未知'}",
        f"- 笔记 ID：`{note_id}`",
        f"- 原文链接：https://www.xiaohongshu.com/explore/{note_id}",
        f"- 发布时间：{format_time(note.get('time'))}",
        f"- 点赞：{note.get('liked_count') or 0}",
        f"- 收藏：{note.get('collected_count') or 0}",
        f"- 分享：{note.get('share_count') or 0}",
        f"- 一级评论：{len(roots)}",
        f"- 二级回复：{reply_count}",
        f"- 评论总数：{len(comments)}",
        "",
        "## 笔记正文",
        "",
    ]
    lines.extend(quote_lines(note.get("desc"), ""))

    images = parse_images(note.get("image_list"))
    if images:
        lines.extend(["", "## 图片", ""])
        lines.extend(f"{index}. {url}" for index, url in enumerate(images, 1))

    lines.extend(["", "## 评论与回复", ""])
    for index, root in enumerate(roots, 1):
        lines.extend(
            render_comment(
                root,
                comments_by_id,
                children,
                "",
                f"{index}. ",
            )
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output.resolve()),
                "roots": len(roots),
                "replies": reply_count,
                "total": len(comments),
                "bytes": output.stat().st_size,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
