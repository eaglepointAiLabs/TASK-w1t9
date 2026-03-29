import pytest

from app.services.errors import AppError
from app.services.password_policy import validate_password_complexity


def test_password_policy_accepts_strong_password():
    validate_password_complexity("StrongPass#123")


@pytest.mark.parametrize(
    "password",
    [
        "short",
        "alllowercase123!",
        "ALLUPPERCASE123!",
        "NoNumberSymbol!",
        "NoSpecial12345",
    ],
)
def test_password_policy_rejects_invalid_password(password):
    with pytest.raises(AppError) as exc:
        validate_password_complexity(password)

    assert exc.value.code == "password_policy_failed"
