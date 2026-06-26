from .settings import settings

PLATFORM = settings.platform
XHS_INTERNATIONAL = settings.xhs_international

KEYWORDS = ""
LOGIN_TYPE = "qrcode"
COOKIES = ""
CRAWLER_TYPE = "search"

HEADLESS = settings.headless
SAVE_LOGIN_STATE = True

CDP_CONNECT_EXISTING = settings.cdp_connect_existing
USER_DATA_DIR = "%s_user_data_dir"

SAVE_DATA_OPTION = settings.save_data_option
SAVE_DATA_PATH = ""

START_PAGE = 1
CRAWLER_MAX_NOTES_COUNT = settings.crawler_max_notes_count
MAX_CONCURRENCY_NUM = 1

ENABLE_GET_COMMENTS = True
# Keep the historical misspelled constant for compatibility with upstream code.
CRAWLER_MAX_COMMENTS_COUNT_SINGLE_NOTE = settings.crawler_max_comments_count_single_note
CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = CRAWLER_MAX_COMMENTS_COUNT_SINGLE_NOTE
ENABLE_GET_SUB_COMMENTS = False

CRAWLER_MIN_SLEEP_SEC = settings.crawler_min_sleep_sec
CRAWLER_MAX_SLEEP_SEC = settings.crawler_max_sleep_sec
DISABLE_SSL_VERIFY = False

# Preserve the original MediaCrawler config import convention.
from .xhs_config import *
