"""
Security tests for the /uploads/<path> public route.

The route is backed by send_from_directory(UPLOAD_DIR, relative_path).
Werkzeug's safe_join is the only guard needed: it raises NotFound for any
path that would escape UPLOAD_DIR.  No string-prefix checks exist in the
handler — safety is structural, not lexical.

Layout of the data directory (simplified):
    DATA_DIR/
        tablepay.db          ← SQLite database
        uploads/             ← UPLOAD_DIR: the ONLY root we serve from
            <dish_id>/
                photo.png
        backups/             ← BACKUP_DIR: sibling, never reachable
        restore-tests/       ← RESTORE_DIR: sibling, never reachable

The tests below confirm:
  1. Files inside UPLOAD_DIR are served correctly.
  2. Sibling directories (backups/, restore-tests/) are unreachable by
     construction — they are outside UPLOAD_DIR, so safe_join cannot
     produce a path to them.
  3. The SQLite database at DATA_DIR root is unreachable.
  4. Path-traversal attempts using ".." are rejected.
  5. The old double-prefix URL format (uploads/uploads/…) that worked
     under the previous string-stripping handler is now a 404, confirming
     the clean break from the legacy design.
"""
from __future__ import annotations


def _write(path, content: bytes = b"secret"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


# ------------------------------------------------------------------ #
#  1. Legitimate serve                                                  #
# ------------------------------------------------------------------ #

def test_serves_file_from_upload_dir(client, app):
    """A file stored under UPLOAD_DIR/<dish_id>/ is reachable at /uploads/<dish_id>/…"""
    upload_dir = app.config["UPLOAD_DIR"]
    _write(upload_dir / "dish-1" / "photo.png", b"\x89PNG\r\n\x1a\nfake")

    response = client.get("/uploads/dish-1/photo.png")

    assert response.status_code == 200
    assert response.data == b"\x89PNG\r\n\x1a\nfake"


def test_stored_path_url_round_trips_correctly(client, app):
    """
    The URL produced by the serialiser (/uploads/<stored_path>) maps back to
    the file on disk.  stored_path is now anchored to UPLOAD_DIR, so no
    intermediate prefix stripping is required.
    """
    upload_dir = app.config["UPLOAD_DIR"]
    stored_path = "dish-2/burger-abc123.jpg"
    _write(upload_dir / "dish-2" / "burger-abc123.jpg", b"JFIF")

    response = client.get(f"/uploads/{stored_path}")

    assert response.status_code == 200
    assert response.data == b"JFIF"


# ------------------------------------------------------------------ #
#  2. Structural isolation: DATA_DIR siblings are unreachable          #
# ------------------------------------------------------------------ #

def test_backup_dir_is_unreachable(client, app):
    """
    BACKUP_DIR is a sibling of UPLOAD_DIR under DATA_DIR.
    /uploads/backups/… resolves to UPLOAD_DIR/backups/… which does not
    contain backup files — the real backup lives at DATA_DIR/backups/.
    """
    _write(app.config["BACKUP_DIR"] / "dump.sql", b"-- sensitive")

    response = client.get("/uploads/backups/dump.sql")

    assert response.status_code == 404


def test_restore_dir_is_unreachable(client, app):
    _write(app.config["RESTORE_DIR"] / "artifact.bin", b"restore data")

    response = client.get("/uploads/restore-tests/artifact.bin")

    assert response.status_code == 404


def test_sqlite_database_is_unreachable(client, app):
    """
    The SQLite database lives at DATA_DIR/tablepay.db.
    /uploads/tablepay.db resolves to UPLOAD_DIR/tablepay.db — a path that
    does not exist, so the handler returns 404.
    """
    _write(app.config["UPLOAD_DIR"].parent / "tablepay.db", b"SQLite format 3\x00")

    response = client.get("/uploads/tablepay.db")

    assert response.status_code == 404


# ------------------------------------------------------------------ #
#  3. Path-traversal rejection                                         #
# ------------------------------------------------------------------ #

def test_dotdot_traversal_cannot_reach_database(client, app):
    """
    Any "uploads/../" segment is normalised or rejected by Werkzeug before
    the handler runs.  Either way the database must not be served.
    """
    _write(app.config["UPLOAD_DIR"].parent / "tablepay.db", b"SQLite format 3\x00")

    # Werkzeug may issue a 308 redirect to the normalised path, or return 404
    # directly.  The invariant is that the response must never be 200.
    response = client.get("/uploads/../tablepay.db")

    assert response.status_code != 200


def test_dotdot_inside_subpath_is_rejected(client, app):
    _write(app.config["UPLOAD_DIR"].parent / "tablepay.db", b"SQLite format 3\x00")

    response = client.get("/uploads/dish-1/../../../tablepay.db")

    assert response.status_code != 200


# ------------------------------------------------------------------ #
#  4. Legacy double-prefix URLs are no longer served                   #
# ------------------------------------------------------------------ #

def test_old_double_prefix_url_format_is_now_404(client, app):
    """
    The previous handler stripped a leading "uploads/" segment, so the live
    URL for a stored image was /uploads/uploads/<dish_id>/<file>.
    After this refactor stored_path is anchored to UPLOAD_DIR, the correct
    URL is /uploads/<dish_id>/<file>, and the double-prefix form must 404.
    """
    upload_dir = app.config["UPLOAD_DIR"]
    _write(upload_dir / "dish-3" / "photo.png", b"\x89PNG\r\n\x1a\nfake")

    new_url = "/uploads/dish-3/photo.png"
    old_url = "/uploads/uploads/dish-3/photo.png"

    assert client.get(new_url).status_code == 200
    assert client.get(old_url).status_code == 404
