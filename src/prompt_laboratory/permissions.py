"""Workspace roles and centralized authorization rules."""

from __future__ import annotations

from enum import StrEnum


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class WorkspacePermission(StrEnum):
    READ_WORKSPACE = "read_workspace"
    RUN_EXPERIMENTS = "run_experiments"
    MANAGE_MEMBERS = "manage_members"
    MANAGE_WORKSPACE = "manage_workspace"


ROLE_PERMISSIONS: dict[WorkspaceRole, frozenset[WorkspacePermission]] = {
    WorkspaceRole.OWNER: frozenset(WorkspacePermission),
    WorkspaceRole.ADMIN: frozenset(
        {
            WorkspacePermission.READ_WORKSPACE,
            WorkspacePermission.RUN_EXPERIMENTS,
            WorkspacePermission.MANAGE_MEMBERS,
        }
    ),
    WorkspaceRole.EDITOR: frozenset(
        {
            WorkspacePermission.READ_WORKSPACE,
            WorkspacePermission.RUN_EXPERIMENTS,
        }
    ),
    WorkspaceRole.VIEWER: frozenset({WorkspacePermission.READ_WORKSPACE}),
}

INVITABLE_ROLES = frozenset(
    {WorkspaceRole.ADMIN, WorkspaceRole.EDITOR, WorkspaceRole.VIEWER}
)


def parse_role(value: str) -> WorkspaceRole:
    try:
        return WorkspaceRole(value)
    except ValueError as exc:
        raise ValueError(f"Unsupported workspace role: {value}") from exc


def has_permission(role: str | WorkspaceRole, permission: WorkspacePermission) -> bool:
    normalized = parse_role(role) if isinstance(role, str) else role
    return permission in ROLE_PERMISSIONS[normalized]
