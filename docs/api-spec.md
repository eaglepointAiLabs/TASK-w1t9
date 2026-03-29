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

### `GET /api/orders/{id}`

Returns the persisted order snapshot with line-item pricing breakdowns.

## Payments

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
- stores payload hash and verification result
- updates the matching payment transaction when found
- deduplicates repeated callbacks for 24 hours by transaction reference

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

### `GET /api/finance/reconciliation/runs`

Returns reconciliation run summaries.

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

Finance Admin only. Requires a `refund:confirm` nonce and operator password re-entry.

### `GET /api/refunds/{id}`

Returns refund status and refund-event history.

### `GET /api/refunds/risk-events`

Returns recorded refund risk events.

## Community

### `POST /api/community/likes/toggle`
### `POST /api/community/favorites/toggle`

```json
{
  "target_type": "post",
  "target_id": "post-uuid"
}
```

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
### `DELETE /api/community/blocks/{blockedUserId}`

## Moderation and governance

### `GET /api/moderation/queue`

Moderator only. Returns queue items and current state.

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

### `GET /api/admin/ops/rate-limits`

Returns recent persisted rate-limit buckets.

### `GET /api/admin/ops/circuit-breakers`

Returns circuit-breaker state per endpoint.

### `POST /api/admin/ops/backups/run`

Runs an encrypted local backup and retention pruning cycle.

### `POST /api/admin/ops/restore/test`

Decrypts the latest backup into the configured restore-test directory and records a restore run.

## Validation and response notes

- All write endpoints require a valid `X-CSRF-Token` for cookie-backed sessions.
- Manager, Finance Admin, Moderator, and governance routes enforce both route-level and service-level role checks.
- Refund and role-change endpoints also require a valid single-use nonce within five minutes.
- Role changes reject self-mutation and preserve at least one Finance Admin assignment.
- Duplicate callback imports inside the 24-hour dedup window return the same deterministic response payload.
