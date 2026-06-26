# Frontend

The operations console is intentionally static: no npm, no bundler, and no CDN
dependency. FastAPI serves it from `service/static/`.

## Files

- `index.html`: semantic page structure and modal containers.
- `styles.css`: compact operations-console layout.
- `app.js`: state, API client, rendering, event binding, and form submission.

## Page Areas

- Top bar: service readiness, queue size, ready account count, refresh time.
- Overview metrics: running, pending, blocked, notes, comments, account rate.
- Task table: task status, note progress, comment counts, latest message, task
  actions.
- Account panel: account health summary, account rows, health check, cookie
  import, QR login.
- Create task panel: tabbed forms for search, batch search, creator, and notes.
- Data preview: selected task notes, note detail, images, and comments.

## API Configuration

By default, API calls use relative paths. To point the frontend to a separate
backend, set:

```html
<script>
window.__XHS_CONFIG__ = { apiBase: "http://host:8088" };
</script>
```

`app.js` reads this value once at startup.

## Maintenance Rules

- Keep rendering functions small and named by UI area.
- Keep all network calls going through `api()` and `json()`.
- Do not add CDN dependencies unless the deployment path explicitly allows
  internet access.
- Keep task and account field names aligned with `docs/api.md`.
- Keep fixed spacing, widths, colors, and typography in `styles.css`. Inline
  styles are reserved for data-driven values such as progress bar width.
