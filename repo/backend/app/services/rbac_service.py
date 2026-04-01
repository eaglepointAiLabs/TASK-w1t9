from __future__ import annotations

from app.services.errors import AppError


class RBACService:
    def require_roles(self, current_roles: list[str], allowed_roles: list[str]) -> None:
        if not set(current_roles).intersection(set(allowed_roles)):
            raise AppError(
                code="forbidden",
                message="You do not have permission to access this resource.",
                status_code=403,
                details={"required_roles": allowed_roles},
            )
