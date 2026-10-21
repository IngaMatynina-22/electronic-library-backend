"""Local auth and multi-user isolation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.container import build_container
from app.core.config import AppConfig
from app.core.exceptions import (
    AuthenticationError,
    UnauthorizedError,
    UserExistsError,
)


def test_register_login_logout(data_dir: Path):
    c = build_container(AppConfig(data_dir=data_dir))
    user = c.auth.register("alice", "secret12", display_name="Alice")
    assert user.username == "alice"
    assert c.auth.current_user() is not None

    c.auth.logout()
    assert c.auth.current_user() is None

    logged = c.auth.login("alice", "secret12")
    assert logged.id == user.id
    c.shutdown()


def test_duplicate_username_and_bad_password(data_dir: Path):
    c = build_container(AppConfig(data_dir=data_dir))
    c.auth.register("bob", "secret12")
    with pytest.raises(UserExistsError):
        c.auth.register("Bob", "otherpass")
    c.auth.logout()
    with pytest.raises(AuthenticationError):
        c.auth.login("bob", "wrongpassword")
    c.shutdown()


def test_unauthorized_without_login(data_dir: Path):
    c = build_container(AppConfig(data_dir=data_dir))
    with pytest.raises(UnauthorizedError):
        c.books.list()
    c.shutdown()


def test_books_isolated_between_users(data_dir: Path, sample_pdf: Path, tmp_path: Path):
    c = build_container(AppConfig(data_dir=data_dir))
    c.auth.register("owner_a", "secret12")
    # Copy sample so second user can import same bytes under different ownership
    result = c.imports.import_file(sample_pdf)
    assert result.success
    book_a = result.book_id

    c.auth.logout()
    c.auth.register("owner_b", "secret12")
    assert c.books.list() == []
    with pytest.raises(Exception):
        c.books.get(book_a)

    # Same file hash is allowed for another user
    other_pdf = tmp_path / "copy.pdf"
    other_pdf.write_bytes(sample_pdf.read_bytes())
    result_b = c.imports.import_file(other_pdf)
    assert result_b.success
    assert result_b.book_id != book_a
    assert len(c.books.list()) == 1
    c.shutdown()


def test_list_usernames(data_dir: Path):
    c = build_container(AppConfig(data_dir=data_dir))
    c.auth.register("carol", "secret12")
    c.auth.logout()
    names = c.auth.list_usernames()
    assert "carol" in names
    c.shutdown()
