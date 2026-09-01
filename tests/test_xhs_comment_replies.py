import unittest
from unittest.mock import AsyncMock, patch

from media_platform.xhs.client import XiaoHongShuClient


class XhsCommentRepliesTest(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_reply_option_bypasses_global_default(self):
        client = object.__new__(XiaoHongShuClient)
        root = {
            "id": "root-1",
            "note_id": "note-1",
            "sub_comments": [{"id": "reply-1", "note_id": "note-1"}],
            "sub_comment_has_more": False,
        }
        client.get_note_comments = AsyncMock(
            return_value={"has_more": False, "cursor": "", "comments": [root]}
        )
        callback = AsyncMock()

        with patch("media_platform.xhs.client.config.ENABLE_GET_SUB_COMMENTS", False):
            comments = await client.get_note_all_comments(
                note_id="note-1",
                xsec_token="token",
                crawl_interval=0,
                callback=callback,
                max_count=10,
                include_sub_comments=True,
            )

        self.assertEqual([item["id"] for item in comments], ["root-1", "reply-1"])
        self.assertEqual(callback.await_count, 2)


if __name__ == "__main__":
    unittest.main()
