import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from core.clerk_auth import verify_session_token
from core.errors import AuthError
from tests.conftest import ADMIN_ORIGIN, POS_ORIGIN


def test_valid_token_returns_claims(make_token, rsa_public_pem):
    claims = verify_session_token(
        make_token(sub="user_1", role="cashier", azp=POS_ORIGIN), rsa_public_pem, [POS_ORIGIN]
    )
    assert claims.sub == "user_1"
    assert claims.role == "cashier"
    assert claims.azp == POS_ORIGIN


def test_expired_token_is_rejected(make_token, rsa_public_pem):
    with pytest.raises(AuthError) as exc:
        verify_session_token(make_token(expires_in=-60), rsa_public_pem, [ADMIN_ORIGIN])
    assert exc.value.code == "TOKEN_EXPIRED"


def test_token_for_other_app_is_rejected(make_token, rsa_public_pem):
    """AU-3: a token minted for pos-web must not work on the admin API."""
    with pytest.raises(AuthError) as exc:
        verify_session_token(make_token(azp=POS_ORIGIN), rsa_public_pem, [ADMIN_ORIGIN])
    assert exc.value.code == "TOKEN_WRONG_APP"


def test_token_without_azp_is_rejected(make_token, rsa_public_pem):
    with pytest.raises(AuthError) as exc:
        verify_session_token(make_token(azp=None), rsa_public_pem, [ADMIN_ORIGIN])
    assert exc.value.code == "TOKEN_WRONG_APP"


def test_token_signed_by_another_key_is_rejected(make_token, rsa_public_pem):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(AuthError) as exc:
        verify_session_token(make_token(key=other), rsa_public_pem, [ADMIN_ORIGIN])
    assert exc.value.code == "TOKEN_INVALID"


def test_garbage_token_is_rejected(rsa_public_pem):
    with pytest.raises(AuthError) as exc:
        verify_session_token("not-a-jwt", rsa_public_pem, [ADMIN_ORIGIN])
    assert exc.value.code == "TOKEN_INVALID"


def test_missing_role_gives_none(make_token, rsa_public_pem):
    claims = verify_session_token(make_token(role=None), rsa_public_pem, [ADMIN_ORIGIN])
    assert claims.role is None


def test_trailing_slash_in_parties_is_tolerated(make_token, rsa_public_pem):
    claims = verify_session_token(make_token(), rsa_public_pem, [ADMIN_ORIGIN + "/"])
    assert claims.sub == "user_admin"


def test_server_without_key_refuses(make_token):
    with pytest.raises(AuthError) as exc:
        verify_session_token(make_token(), None, [ADMIN_ORIGIN])
    assert exc.value.code == "AUTH_NOT_CONFIGURED"
