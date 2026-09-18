from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from prompt_laboratory.permissions import (
    INVITABLE_ROLES,
    WorkspacePermission,
    WorkspaceRole,
    has_permission,
    parse_role,
)


def test_role_permission_matrix_is_least_privilege() -> None:
    assert has_permission(WorkspaceRole.OWNER, WorkspacePermission.MANAGE_WORKSPACE)
    assert has_permission("admin", WorkspacePermission.MANAGE_MEMBERS)
    assert has_permission("editor", WorkspacePermission.RUN_EXPERIMENTS)
    assert has_permission("viewer", WorkspacePermission.READ_WORKSPACE)

    assert not has_permission("admin", WorkspacePermission.MANAGE_WORKSPACE)
    assert not has_permission("editor", WorkspacePermission.MANAGE_MEMBERS)
    assert not has_permission("viewer", WorkspacePermission.RUN_EXPERIMENTS)
    assert WorkspaceRole.OWNER not in INVITABLE_ROLES


def test_unknown_role_is_rejected() -> None:
    try:
        parse_role("super-admin")
    except ValueError as exc:
        assert str(exc) == "Unsupported workspace role: super-admin"
    else:
        raise AssertionError("Unknown workspace role was accepted")


def test_invitation_migration_upgrades_existing_database(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'phase9c.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "0003")
    command.upgrade(config, "head")

    inspector = inspect(create_engine(database_url))
    assert "workspace_invitations" in inspector.get_table_names()

    columns = {column["name"]: column for column in inspector.get_columns("workspace_invitations")}
    assert set(columns) == {
        "id",
        "workspace_id",
        "inviter_user_id",
        "invited_email",
        "role",
        "token_hash",
        "status",
        "expires_at",
        "created_at",
        "responded_at",
    }
    assert columns["responded_at"]["nullable"] is True
    assert columns["token_hash"]["nullable"] is False

    unique_columns = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("workspace_invitations")
    }
    assert ("token_hash",) in unique_columns
