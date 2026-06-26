# Configuration

`config/` bridges the original MediaCrawler configuration shape with this
focused XHS service.

- `settings.py`: typed environment-backed settings used by the service.
- `base_config.py`: compatibility constants expected by upstream XHS modules.
- `db_config.py`: database path configuration.
- `xhs_config.py`: XHS-specific compatibility settings.

Prefer adding new service configuration to `settings.py`. Keep compatibility
aliases in `base_config.py` when upstream modules still import historical names.
