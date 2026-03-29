## Original Prompt

Build a TablePay Restaurant Ordering & Community system with offline payment capture/reconciliation, secure refund handling, rich dish/option modeling, high-concurrency ordering performance, and community governance.

Key expectations include:

- English server-rendered UI enhanced by HTMX.
- Dish filtering by category, tags, availability windows, sold-out status.
- Required options (spice level, soup base, portion size) enforced before checkout.
- Store Manager controls for publish/unpublish, sort order, images, add-ons, and size upcharges.
- Image upload validation: JPEG/PNG only, max 2 MB, preview + error feedback.
- Finance Admin offline payment operations:
  - Local WeChat Pay JSAPI-compatible simulator support.
  - CSV statement import and reconciliation with variance/exception workflow.
- Community actions: like, favorite, comment, report abuse, block users.
- Moderator queue with reason codes, outcomes, and action throttling/cooldown communication.
- Flask backend + REST-style endpoints + server-side validation + consistent errors.
- SQLite persistence for users, roles, dishes, options, inventory, payments, refunds, reconciliation, moderation.
- Local auth: bcrypt, min 12 chars, lockout after 10 failed attempts in 15 minutes, CSRF protection.
- Anti-replay nonces (5-minute expiry) for refunds and role changes.
- Offline callback package signature verification with encrypted rotating keys.
- 24-hour callback idempotency by transaction reference.
- Refund policy: partial/multiple up to captured amount, original-route enforced, step-up for > $50 or anomalies.
- Async job processing, cache TTLs, rate limiting, circuit breaking, structured exception logging.
- Nightly encrypted backups retained 14 days + tested offline restore procedure.

---
