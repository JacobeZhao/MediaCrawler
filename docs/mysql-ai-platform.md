# MySQL ai_platform 数据库

本项目需要连接一个外部 MySQL 库用于后续数据同步/分析。连接参数保存在项目根目录 `.env`，该文件已被 `.gitignore` 忽略，不提交到版本库。

## 连接配置

`.env` 中记录：

```env
MYSQL_HOST=...
MYSQL_PORT=3306
MYSQL_USER=...
MYSQL_PASSWORD=...
```

当前可访问业务库：

- `ai_platform`

## 核心小红书数据表

原始笔记表：

- `ods_xhs_notes_di`
- 当前行数约 1121
- 关键字段：`note_id`, `publish_time`, `user_id`, `nickname`, `title`, `desc`, `comment_cnt`, `liked_cnt`, `collected_cnt`, `source_keyword`, `note_url`, `image_list`, `tag_list`, `process_time`

原始评论表：

- `ods_xhs_comments_di`
- 当前行数约 36157
- 关键字段：`comment_id`, `note_id`, `content`, `comment_level`, `parent_comment_id`, `parent_content`, `like_cnt`, `create_time`, `user_id`, `nickname`, `source_keyword`, `keyword_category`, `keyword_update_cycle`, `keyword_period_label`, `note_publish_time`, `process_time`

处理后评论线程表：

- `dwd_xhs_comment_threads_df`
- 当前行数约 28378
- 关键字段：`comment_id`, `note_id`, `content`, `thread_text`, `label_id`, `label_name`, `l1_tag_id`, `l1_tag_name`, `l2_tag_id`, `l2_tag_name`, `l3_tag_name`, `is_valuable`, `reply_cnt`, `source_keyword`, `keyword_category`, `keyword_update_cycle`, `keyword_period_label`, `process_time`

## 相关维表

- `dim_xhs_keyword_period_df`：关键词周期维表，包含 `category`, `keyword`, `update_cycle`, `period_label`, `active_from`, `active_to`
- `dim_xhs_comment_source_period_df`：评论来源周期维表，包含 `category`, `source_keyword`, `search_index`, `update_cycle`, `period_label`, `active_from`, `active_to`

## 探测脚本归档

本地临时探测脚本已经从项目根目录移到 `data_archive/tmp_20260626/`，包括：

- `.tmp_mysql_probe.py`：测试连接并列出可见数据库
- `.tmp_mysql_schema_probe.py`：只读输出 `ai_platform` 表名、行数和字段

后续如需长期维护，应整理成 `tools/` 下的正式只读诊断工具，不再放回项目根目录。
