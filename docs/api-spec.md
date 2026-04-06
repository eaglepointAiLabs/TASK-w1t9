# TablePay API Spec

## Error contract

All JSON errors use:

```json
{
  "code": "string",
  "message": "Human readable message",
  "details": {}
}
```

`details` is sanitized before it is logged or returned. Only explicitly safe diagnostic fields are exposed; sensitive keys such as secrets, tokens, nonces, passwords, and session identifiers are redacted or omitted.

All response timestamps are serialized in UTC ISO 8601 form with a trailing `Z`.

List endpoints support optional `page` and `page_size` query parameters.

When a list endpoint returns JSON, the response includes a `pagination` object:

```json
{
  "page": 1,
  "page_size": 20,
  "total_items": 42,
  "total_pages": 3,
  "has_next": true,
  "has_prev": false
}
```

For HTMX-style progressive enhancement requests, the server can also return:

- `X-Toast-Message`
- `X-Toast-Tone`
- `X-Redirect-Location`
- `X-Error-Code`

## Authentication

### `POST /auth/login`

Authenticate a local user.

```json
{
  "username": "customer",
  "password": "Customer#1234"
}
```

Headers:

- `X-CSRF-Token`: required

### `POST /auth/register`

Register a new Customer account and create a session.

```json
{
  "username": "fresh.customer",
  "password": "FreshCustomer#123",
  "confirm_password": "FreshCustomer#123"
}
```

Validation:

- username is sanitized to lowercase and must match `^[a-z0-9][a-z0-9._-]{2,31}$`
- password must satisfy complexity policy (12+ chars, upper, lower, digit, symbol)

Headers:

- `X-CSRF-Token`: required

### `POST /auth/logout`

Invalidate the active session cookie.

Headers:

- `X-CSRF-Token`: required

### `GET /auth/me`

Return the current authenticated identity.

### `POST /api/auth/nonces`

Authenticated users request single-use nonces for replay-protected actions.

```json
{
  "purpose": "refund:create"
}
```

## Catalog

### `GET /api/dishes`

Query parameters:

- `category`
- `tag` repeatable
- `available_at` in ISO 8601 datetime format; offset-aware values are normalized to UTC before filtering
- `include_sold_out=1`
- `page` optional positive integer
- `page_size` optional positive integer

### `GET /api/dishes/{id}`

Returns a single dish with option groups and image metadata.

### `POST /api/dishes/{id}/selection-check`

Validates required option selections before cart entry.

### `POST /api/manager/dishes`

Store Manager only. Creates dishes with options, tags, and availability windows.

### `PATCH /api/manager/dishes/{id}`

Store Manager only. Accepts full dish updates including sort order, sold-out state, archive flag, tags, windows, and pricing options.

### `POST /api/manager/dishes/{id}/publish`

Store Manager only.

```json
{ "publish": true }
```

### `POST /api/manager/dishes/bulk-update`

Store Manager only. Queues an async bulk mutation job.

```json
{
  "dish_ids": ["dish-uuid-1", "dish-uuid-2"],
  "publish": true,
  "archived": false
}
```

Response returns `202 Accepted` with an ops `job_id`.

### `POST /api/manager/dishes/{id}/images`

Store Manager only. Multipart form-data with field name `image`.

Validation:

- JPEG or PNG only
- Maximum 2 MB

## Cart and orders

### `GET /api/cart`

Returns the active cart with line items, selected options, and persisted pricing breakdowns.

### `POST /api/cart/items`

```json
{
  "dish_id": "dish-uuid",
  "quantity": 2,
  "selected_options": {
    "addons": ["avocado"]
  }
}
```

### `PATCH /api/cart/items/{id}`

Updates quantity and or selected options. Required option rules are revalidated on every mutation.

### `DELETE /api/cart/items/{id}`

Removes the line item from the active cart.

### `POST /api/orders/checkout`

```json
{
  "checkout_key": "client-generated-idempotency-key"
}
```

Behavior:

- Revalidates sold-out state and availability windows at submit time
- Prevents negative inventory
- Returns the existing order when the same user retries the same `checkout_key`

### `GET /api/orders`

Returns the authenticated user's orders.

Query parameters:

- `page` optional positive integer
- `page_size` optional positive integer

### `GET /api/orders/{id}`

Returns the persisted order snapshot with line-item pricing breakdowns.

## Payments

### `GET /api/payments`

Finance Admin only. Returns payment transactions.

Query parameters:

- `page` optional positive integer
- `page_size` optional positive integer

### `POST /api/payments/capture`

Finance Admin only.

```json
{
  "order_id": "order-uuid",
  "transaction_reference": "wechat-local-0001",
  "capture_amount": "10.25",
  "status": "pending"
}
```

### `POST /api/payments/callbacks/verify`

Finance Admin only. Verifies a callback package without applying it.

```json
{
  "key_id": "simulator-v1",
  "signature": "hex-hmac",
  "transaction_reference": "wechat-local-0001",
  "payload": {
    "transaction_reference": "wechat-local-0001",
    "status": "success",
    "occurred_at": "2026-03-28T10:00:00+00:00"
  }
}
```

### `POST /api/payments/callbacks/import`

Finance Admin only. Accepts the same package shape via JSON or uploaded file contents.

Behavior:

- verifies signature using encrypted stored keys
- requires `payload.occurred_at` to be a valid ISO 8601 datetime value
- stores payload hash and verification result
- updates the matching payment transaction when found
- deduplicates repeated callbacks for 24 hours by transaction reference

### `POST /api/payments/jsapi/simulate`

Finance Admin only. Generates a signed simulator callback package and imports it through the same verification and dedup flow used by callback imports.

```json
{
  "transaction_reference": "wechat-local-0001",
  "status": "success",
  "key_id": "simulator-v1"
}
```

### `GET /api/payments/{id}`

Finance Admin only. Returns payment transaction details and callback verification history without exposing key plaintext.

## Reconciliation

### `POST /api/finance/reconciliation/import`

Finance Admin only.

```json
{
  "source_name": "terminal_csv",
  "filename": "terminal.csv",
  "statement_csv": "transaction_reference,amount,currency,status\nwechat-local-0001,10.25,USD,success\n"
}
```

Variance types:

- `missing_local_transaction`
- `amount_mismatch`
- `duplicate_reference`
- `status_mismatch`

`POST /api/finance/reconciliation/import` also accepts `{"async": true}` to queue processing and return `202 Accepted` with a `job_id`.

### `POST /api/finance/reconciliation/import/async`

Finance Admin only. Always queues reconciliation processing as an async ops job and returns `202 Accepted`.

### `GET /api/finance/reconciliation/runs`

Returns reconciliation run summaries.

Query parameters:

- `page` optional positive integer
- `page_size` optional positive integer

### `GET /api/finance/reconciliation/runs/{id}`

Returns a reconciliation run with row and exception details.

### `POST /api/finance/reconciliation/exceptions/{id}/resolve`

Finance Admin only.

```json
{
  "action_type": "resolve",
  "reason": "Accepted mismatch after manual review."
}
```

## Refunds

### `POST /api/refunds`

Finance Admin only. Requires a `refund:create` nonce.

```json
{
  "transaction_reference": "wechat-local-0001",
  "refund_amount": "12.00",
  "route": "offline_wechat_simulator",
  "nonce": "single-use-nonce"
}
```

### `POST /api/refunds/{id}/confirm-stepup`

Store Manager only. Requires a `refund:approve` nonce and manager password re-entry.

### `GET /api/refunds/{id}`

Returns refund status and refund-event history.

### `GET /api/refunds/risk-events`

Returns recorded refund risk events.

Query parameters:

- `page` optional positive integer
- `page_size` optional positive integer

## Community

### `GET /api/community/posts`

Authenticated users only. Returns community posts.

Query parameters:

- `page` optional positive integer
- `page_size` optional positive integer

### `POST /api/community/likes/toggle`

### `POST /api/community/favorites/toggle`

```json
{
  "target_type": "post",
  "target_id": "post-uuid"
}
```

`target_id` must reference an existing object for the provided `target_type`.

### `POST /api/community/comments`

```json
{
  "target_type": "post",
  "target_id": "post-uuid",
  "body": "Nice review"
}
```

Failure cases include `cooldown_active`, `throttled`, and `blocked_interaction`.

### `POST /api/community/reports`

Allowed `reason_code` values:

- `abuse`
- `spam`
- `harassment`
- `other`

### `POST /api/community/blocks`

`blocked_user_id` must reference an existing user. Returns `404` if the target user does not exist.

### `DELETE /api/community/blocks/{blockedUserId}`

## Moderation and governance

### `GET /api/moderation/queue`

Moderator only. Returns queue items and current state.

Query parameters:

- `page` optional positive integer
- `page_size` optional positive integer

### `POST /api/moderation/items/{id}/decision`

Moderator only.

```json
{
  "outcome": "remove",
  "reason_code": "abuse_content",
  "operator_notes": "Confirmed abusive content."
}
```

Required outcomes:

- `dismiss`
- `warn`
- `hide`
- `remove`
- `suspend`

### `GET /api/moderation/items/{id}/history`

Moderator only. Returns the full moderation timeline for the item.

### `POST /api/admin/roles/change`

Finance Admin only. Replay-protected governance endpoint.

```json
{
  "target_username": "customer",
  "role_name": "Moderator",
  "action": "grant",
  "nonce": "single-use-admin-role-change-nonce"
}
```

## Operations

### `GET /api/admin/ops/jobs`

Returns queued, running, completed, and dead-letter jobs.

Query parameters:

- `page` optional positive integer
- `page_size` optional positive integer

### `POST /api/admin/ops/jobs/process`

Finance Admin only. Processes queued jobs immediately.

```json
{
  "count": 1
}
```

### `GET /api/admin/ops/rate-limits`

Returns recent persisted rate-limit buckets.

Query parameters:

- `page` optional positive integer
- `page_size` optional positive integer

### `GET /api/admin/ops/circuit-breakers`

Returns circuit-breaker state per endpoint.

Query parameters:

- `page` optional positive integer
- `page_size` optional positive integer

### `POST /api/admin/ops/backups/run`

Runs an encrypted local backup and retention pruning cycle.

Nightly automation:

- Runtime maintenance automatically triggers one nightly encrypted backup per UTC day once `NIGHTLY_BACKUP_HOUR_UTC` has passed.
- Scheduled backup runs are recorded in `backup_jobs` with `trigger=nightly_scheduler`.

### `POST /api/admin/ops/restore/test`

Decrypts the latest backup into the configured restore-test directory and records a restore run.

## Validation and response notes

- All write endpoints require a valid `X-CSRF-Token` for cookie-backed sessions.
- All API endpoints that require authorization check authentication first: unauthenticated callers always receive `401` before any `403` role check is evaluated.
- Manager, Finance Admin, Moderator, and governance routes enforce both route-level and service-level role checks.
- Refund and role-change endpoints also require a valid single-use nonce within five minutes.
- Role changes reject self-mutation and preserve at least one Finance Admin assignment.
- Duplicate callback imports inside the 24-hour dedup window return the same deterministic response payload.
