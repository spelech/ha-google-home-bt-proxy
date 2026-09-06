"""Scaffolding smoke test."""
import pathlib


def test_repo_structure():
    """Verify essential repository files exist."""
    repo_root = pathlib.Path(__file__).parent.parent
    assert (repo_root / "pyproject.toml").is_file()
    assert (repo_root / "AGENTS.md").is_file()
    assert (repo_root / "custom_components" / "google_home_bt_proxy").is_dir()
