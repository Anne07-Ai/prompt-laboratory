"""Role-aware helpers for the workspace collaboration dashboard."""

from collections.abc import Iterable


def can_manage_members(role: str) -> bool:
    """Return whether a workspace role may render membership controls."""
    return role in {"owner", "admin"}


def manageable_members(
    members: Iterable[dict[str, object]],
    *,
    actor_user_id: str,
    actor_role: str,
) -> list[dict[str, object]]:
    """Filter members to targets the actor may attempt to manage."""
    if not can_manage_members(actor_role):
        return []
    return [
        member
        for member in members
        if str(member["user_id"]) != actor_user_id
        and not (
            actor_role == "admin"
            and str(member["role"]) in {"owner", "admin"}
        )
    ]
