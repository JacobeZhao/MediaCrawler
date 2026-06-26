# Static Frontend

The operations console is served directly by FastAPI without a build step.

- `index.html`: page structure and modal containers.
- `styles.css`: all fixed layout, spacing, widths, colors, and typography.
- `app.js`: state, API client, rendering, event binding, and form submission.

Keep fixed presentation in `styles.css`. Inline styles are reserved for
data-driven values such as task progress bar width.

The frontend calls relative `/api/*` endpoints by default. To target another
backend, define `window.__XHS_CONFIG__.apiBase` before loading `app.js`.
