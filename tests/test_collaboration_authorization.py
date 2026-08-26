from app.models.workbook import Workbook
from app.permissions.service import PermissionService
from app.storage.json_storage import JsonWorkbookStorage
from server.authorization import JsonWorkbookAuthorizer


def test_json_authorizer_resolves_persisted_workbook_role(tmp_path):
    workbook = Workbook(name="Shared")
    workbook.add_sheet("Sheet1")
    permissions = PermissionService()
    workbook.permissions = permissions.assign_owner({}, "owner@example.com")
    workbook.permissions = permissions.grant_viewer_access(
        workbook.permissions, "viewer@example.com"
    )
    JsonWorkbookStorage().save_workbook(str(tmp_path / "shared.json"), workbook)
    authorizer = JsonWorkbookAuthorizer(tmp_path)

    assert authorizer.resolve_role("owner@example.com", "shared") == "owner"
    assert authorizer.resolve_role("viewer@example.com", "shared") == "viewer"
    assert authorizer.resolve_role("outsider@example.com", "shared") is None


def test_json_authorizer_rejects_path_traversal(tmp_path):
    assert JsonWorkbookAuthorizer(tmp_path).resolve_role(
        "owner@example.com", "../private"
    ) is None
