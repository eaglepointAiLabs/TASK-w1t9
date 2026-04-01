import pytest

from app.services.errors import AppError
from app.services.rbac_service import RBACService


def test_rbac_allows_matching_role():
    RBACService().require_roles(["Customer"], ["Customer", "Moderator"])


def test_rbac_blocks_missing_role():
    with pytest.raises(AppError) as exc:
        RBACService().require_roles(["Customer"], ["Finance Admin"])

    assert exc.value.status_code == 403
