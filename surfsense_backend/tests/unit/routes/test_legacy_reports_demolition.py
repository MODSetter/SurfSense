import ast
import tomllib
from pathlib import Path

from app.routes import router

BACKEND_ROOT = Path(__file__).parents[3]


def test_legacy_reports_and_typst_are_absent() -> None:
    assert [
        route.path for route in router.routes if route.path.startswith("/reports")
    ] == []

    dependencies = tomllib.loads(
        (BACKEND_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["dependencies"]
    assert not any(
        dependency.split(";", 1)[0].strip().startswith("typst")
        for dependency in dependencies
    )

    typst_imports: list[str] = []
    for path in (BACKEND_ROOT / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            (
                isinstance(node, ast.Import)
                and any(alias.name == "typst" for alias in node.names)
            )
            or (isinstance(node, ast.ImportFrom) and node.module == "typst")
            for node in ast.walk(tree)
        ):
            typst_imports.append(str(path.relative_to(BACKEND_ROOT)))

    assert typst_imports == []


def test_document_exports_are_absent_but_workspace_export_remains() -> None:
    route_paths = {route.path for route in router.routes}

    assert "/workspaces/{workspace_id}/documents/{document_id}/export" not in route_paths
    assert (
        "/workspaces/{workspace_id}/documents/{document_id}/download-markdown"
        not in route_paths
    )
    assert "/workspaces/{workspace_id}/export" in route_paths

    template_imports: list[str] = []
    for path in (BACKEND_ROOT / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            (
                isinstance(node, ast.Import)
                and any(
                    alias.name == "app.templates"
                    or alias.name.startswith("app.templates.")
                    for alias in node.names
                )
            )
            or (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and (
                    node.module == "app.templates"
                    or node.module.startswith("app.templates.")
                )
            )
            for node in ast.walk(tree)
        ):
            template_imports.append(str(path.relative_to(BACKEND_ROOT)))

    assert template_imports == []
