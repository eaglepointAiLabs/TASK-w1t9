# TablePay Disaster Recovery Runbook

## Purpose

Provide a repeatable offline drill to verify that encrypted backups can be created, retained, and restored on a new machine without network dependency.

## Scope

- Backup creation using the application backup flow
- Restore validation using the application restore-test flow
- Evidence capture for audit and operational confidence

## Preconditions

- Application is running and healthy
- You have a Finance Admin session (required for ops endpoints)
- The data volume or local data directory is writable
- `KEY_ENCRYPTION_SECRET` used to create backups is available and unchanged for restore

## Frequency

- Minimum: monthly restore drill
- Recommended: weekly for active environments
- Always run after key rotation, backup path changes, or infrastructure migration

## Drill Steps

### 1) Verify service health

- Confirm health endpoint returns success (`/healthz`)
- Record timestamp and host identifier

### 2) Trigger manual backup

Call ops backup endpoint:

- `POST /api/admin/ops/backups/run`

Expected result:

- Response `code=ok`
- Backup job id is returned
- Backup file path is returned
- Backup file exists under backup directory

Evidence to capture:

- Request timestamp
- Response payload
- Backup file path and file size

### 3) Trigger restore test

Call restore validation endpoint:

- `POST /api/admin/ops/restore/test`

Expected result:

- Response `code=ok`
- Restore run id is returned
- Restore output path exists under restore-test directory

Evidence to capture:

- Request timestamp
- Response payload
- Restore file path and file size

### 4) Validate metadata consistency

Check persisted records:

- latest backup job status is `completed`
- latest restore run status is `completed`
- restore run references a valid backup job id

### 5) Validate retention behavior

- Confirm `retention_until` is set on backup record
- Confirm expired backups are pruned on subsequent backup cycles

## Failure Handling

If backup fails:

- Verify backup directory permissions
- Verify SQLite file path exists and is readable
- Verify encryption key configuration is present and valid

If restore fails:

- Verify at least one backup record exists
- Verify backup file still exists on disk
- Verify current `KEY_ENCRYPTION_SECRET` matches the key used during backup creation

## Recovery Drill Acceptance Criteria

All conditions must pass:

- backup endpoint returns success and creates encrypted file
- restore-test endpoint returns success and writes restore artifact
- backup and restore metadata persisted with `completed` status
- runbook evidence artifacts are recorded

## Evidence Template

Record each drill with:

- environment
- operator
- started_at_utc
- backup_job_id
- backup_file_path
- restore_run_id
- restore_file_path
- outcome (`pass` or `fail`)
- notes and remediation actions

## Security Notes

- Do not expose backup content in logs
- Protect `KEY_ENCRYPTION_SECRET` via secure secret handling
- Keep restore artifacts in controlled directories and clean up after validation
- Never enable demo seed credentials in production environments
