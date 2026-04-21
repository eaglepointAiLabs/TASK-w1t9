"""reanchor dish_images.stored_path from DATA_DIR-relative to UPLOAD_DIR-relative

Previously, stored_path was computed as destination_path.relative_to(upload_root.parent),
which produced paths like "uploads/<dish_id>/<file>".  The route handler compensated by
stripping the leading "uploads/" segment at serve time — a string-check, not a structural
guarantee.

This migration strips the prefix from any existing row so that stored_path becomes
"<dish_id>/<file>", relative to UPLOAD_DIR itself.  After this change, serve_upload can
call send_from_directory(UPLOAD_DIR, stored_path) directly with no manipulation.
"""

from alembic import op
import sqlalchemy as sa


revision = "20260328_0010"
down_revision = "20260328_0009"
branch_labels = None
depends_on = None

_PREFIX = "uploads/"
_PREFIX_LEN = len(_PREFIX)  # 8


def upgrade():
    # SUBSTR is 1-indexed; position (_PREFIX_LEN + 1) skips the "uploads/" prefix.
    op.execute(
        sa.text(
            f"UPDATE dish_images "
            f"SET stored_path = SUBSTR(stored_path, {_PREFIX_LEN + 1}) "
            f"WHERE stored_path LIKE '{_PREFIX}%'"
        )
    )


def downgrade():
    op.execute(
        sa.text(
            f"UPDATE dish_images "
            f"SET stored_path = '{_PREFIX}' || stored_path "
            f"WHERE stored_path NOT LIKE '{_PREFIX}%'"
        )
    )
