"""Tests for authentication and password handling."""

from __future__ import annotations

import pytest

from server.app.auth.password import hash_password, verify_password
from server.app.auth.session import authenticate_user, change_password
from server.app.models.user import User


class TestPasswordHashing:
    def test_round_trip(self):
        h = hash_password("correct horse battery staple")
        assert verify_password("correct horse battery staple", h)

    def test_wrong_password_fails(self):
        h = hash_password("p@ssw0rd")
        assert not verify_password("p@ssword", h)

    def test_empty_password_raises(self):
        with pytest.raises(ValueError):
            hash_password("")

    def test_empty_password_does_not_verify(self):
        h = hash_password("p@ssw0rd")
        assert not verify_password("", h)

    def test_whitespace_only_is_treated_as_empty(self):
        with pytest.raises(ValueError):
            hash_password("   ")

    def test_hash_is_not_plaintext(self):
        plain = "p@ssw0rd-secret"
        h = hash_password(plain)
        assert plain not in h
        assert h != plain
        # Bcrypt hashes start with $2 (any variant)
        assert h.startswith("$2")


class TestAuthenticateUser:
    @pytest.fixture
    def make_user(self, db_session):
        def _factory(username="alice", password="hunter22@@", active=True, role="visitor"):
            u = User(
                username=username,
                password_hash=hash_password(password),
                role=role,
                is_active=active,
            )
            db_session.add(u)
            db_session.commit()
            return u

        return _factory

    def test_valid_credentials_returns_user(self, db_session, make_user):
        make_user(username="alice", password="hunter22@@")
        u = authenticate_user(db_session, "alice", "hunter22@@")
        assert u is not None
        assert u.username == "alice"

    def test_wrong_password_returns_none(self, db_session, make_user):
        make_user(username="alice", password="hunter22@@")
        assert authenticate_user(db_session, "alice", "wrong") is None

    def test_unknown_user_returns_none(self, db_session):
        assert authenticate_user(db_session, "nobody", "any") is None

    def test_inactive_user_cannot_log_in(self, db_session, make_user):
        make_user(username="alice", password="hunter22@@", active=False)
        assert authenticate_user(db_session, "alice", "hunter22@@") is None

    def test_username_is_trimmed(self, db_session, make_user):
        make_user(username="alice", password="hunter22@@")
        assert authenticate_user(db_session, "  alice  ", "hunter22@@") is not None

    def test_empty_username_returns_none(self, db_session):
        assert authenticate_user(db_session, "", "x") is None


class TestChangePassword:
    @pytest.fixture
    def user(self, db_session):
        u = User(
            username="bob",
            password_hash=hash_password("oldpass123"),
            role="visitor",
            is_active=True,
            must_change_password=True,
        )
        db_session.add(u)
        db_session.commit()
        return u

    def test_change_password_with_correct_current(self, db_session, user):
        change_password(db_session, user.id, "oldpass123", "newpass1234")
        db_session.refresh(user)
        assert verify_password("newpass1234", user.password_hash)
        assert user.must_change_password is False

    def test_wrong_current_password_rejected(self, db_session, user):
        with pytest.raises(ValueError):
            change_password(db_session, user.id, "wrong", "newpass1234")

    def test_too_short_new_password_rejected(self, db_session, user):
        with pytest.raises(ValueError):
            change_password(db_session, user.id, "oldpass123", "short")

    def test_inactive_user_cannot_change_password(self, db_session, user):
        user.is_active = False
        db_session.commit()
        with pytest.raises(ValueError):
            change_password(db_session, user.id, "oldpass123", "newpass1234")
