# Backup Directory Policy

The following directory is a historical backup created during the cleanup:

```text
_backup_before_cleanup_20260625_102946/
```

Do not use this directory for future development.

Rules:

- Do not read it during normal code exploration.
- Do not search inside it.
- Do not import, reference, or copy code from it unless explicitly requested.
- Do not modify or delete it unless explicitly requested.

Current source of truth is the cleaned service code outside this backup directory.
