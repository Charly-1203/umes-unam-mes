import pytest
from sqlmodel import select

from mes_core.enums import Role
from mes_server.auth.passwords import verify_password
from mes_server.db.models import User
from mes_server.services import users
from mes_server.services.errors import AlreadyExistsError, ValidationError


def new_user(session, username="ada", password="secret123", role=Role.ADMIN, **extra):
    user = users.create_user(
        session,
        username=username,
        full_name=extra.get("full_name", "Ada Lovelace"),
        password=password,
        role=role,
    )
    session.commit()
    return user


def test_create_user_stores_a_hash_not_the_password(session):
    user = new_user(session)
    assert user.id is not None
    assert user.password_hash != "secret123"
    assert verify_password("secret123", user.password_hash)[0]


def test_username_is_normalized(session):
    assert new_user(session, username="  Ada.Lovelace ").username == "ada.lovelace"


def test_full_name_is_trimmed(session):
    assert new_user(session, full_name="  Ada  ").full_name == "Ada"


@pytest.mark.parametrize("username", ["ab", "with space", "ñandu", "-starts-with-dash", "x" * 65])
def test_invalid_usernames_are_rejected(session, username):
    with pytest.raises(ValidationError, match="Username"):
        new_user(session, username=username)


@pytest.mark.parametrize("password", ["short", "        "])
def test_weak_passwords_are_rejected(session, password):
    with pytest.raises(ValidationError, match="Password"):
        new_user(session, password=password)


def test_blank_full_name_is_rejected(session):
    with pytest.raises(ValidationError, match="Full name"):
        new_user(session, full_name="   ")


def test_duplicate_username_is_rejected_ignoring_case(session):
    new_user(session, username="ada")
    with pytest.raises(AlreadyExistsError):
        new_user(session, username="ADA")


def test_authenticate_with_valid_credentials(session):
    new_user(session)
    assert users.authenticate(session, "ada", "secret123").username == "ada"


def test_authenticate_ignores_username_case(session):
    new_user(session)
    assert users.authenticate(session, " ADA ", "secret123") is not None


def test_authenticate_rejects_wrong_password(session):
    new_user(session)
    assert users.authenticate(session, "ada", "wrong-password") is None


def test_authenticate_rejects_unknown_user(session):
    assert users.authenticate(session, "nobody", "secret123") is None


def test_authenticate_rejects_inactive_user(session):
    user = new_user(session)
    user.is_active = False
    session.commit()
    assert users.authenticate(session, "ada", "secret123") is None


def test_authenticate_upgrades_outdated_hash(session, monkeypatch):
    user = new_user(session)
    monkeypatch.setattr(users, "verify_password", lambda *_: (True, "upgraded-hash"))
    users.authenticate(session, "ada", "secret123")
    session.commit()
    assert session.exec(select(User)).one().password_hash == "upgraded-hash"
    assert user.password_hash == "upgraded-hash"


def test_list_users_is_ordered_by_username(session):
    new_user(session, username="zoe")
    new_user(session, username="ana", role=Role.OPERATOR)
    assert [user.username for user in users.list_users(session)] == ["ana", "zoe"]


def test_count_active_admins(session):
    assert users.count_active_admins(session) == 0
    new_user(session, username="admin1")
    inactive = new_user(session, username="admin2")
    new_user(session, username="operator", role=Role.OPERATOR)
    inactive.is_active = False
    session.commit()
    assert users.count_active_admins(session) == 1
