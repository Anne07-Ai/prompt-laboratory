from prompt_laboratory.dashboard_collaboration import (
    can_manage_members,
    manageable_members,
)

MEMBERS = [
    {"user_id": "owner", "role": "owner"},
    {"user_id": "admin-one", "role": "admin"},
    {"user_id": "admin-two", "role": "admin"},
    {"user_id": "editor", "role": "editor"},
    {"user_id": "viewer", "role": "viewer"},
]


def test_only_owner_and_admin_render_member_management() -> None:
    assert can_manage_members("owner")
    assert can_manage_members("admin")
    assert not can_manage_members("editor")
    assert not can_manage_members("viewer")


def test_owner_can_manage_every_other_member() -> None:
    targets = manageable_members(
        MEMBERS,
        actor_user_id="owner",
        actor_role="owner",
    )
    assert {target["user_id"] for target in targets} == {
        "admin-one",
        "admin-two",
        "editor",
        "viewer",
    }


def test_admin_cannot_manage_self_owner_or_other_admins() -> None:
    targets = manageable_members(
        MEMBERS,
        actor_user_id="admin-one",
        actor_role="admin",
    )
    assert {target["user_id"] for target in targets} == {"editor", "viewer"}


def test_editor_and_viewer_have_no_management_targets() -> None:
    assert manageable_members(MEMBERS, actor_user_id="editor", actor_role="editor") == []
    assert manageable_members(MEMBERS, actor_user_id="viewer", actor_role="viewer") == []
