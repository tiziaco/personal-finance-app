"""Every module under app/modules/ is wired into the three places a fork must not forget.

R1 and R6 are import-linter contracts in pyproject.toml; a module without one is
simply unchecked. alembic/env.py is the models registry (R8); a models slot it
does not import is a table Alembic never sees. app/main.py imports every module
by name so that subscribers register even for a module with no router.
"""

import ast
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SERVER = Path(__file__).resolve().parents[2]
MODULES_DIR = SERVER / "app" / "modules"


def _modules() -> list[str]:
    return sorted(p.name for p in MODULES_DIR.iterdir() if p.is_dir() and p.name != "__pycache__")


def _contracts() -> list[dict]:
    config = tomllib.loads((SERVER / "pyproject.toml").read_text())
    return config["tool"]["importlinter"]["contracts"]


def _has_models_slot(name: str) -> bool:
    return (MODULES_DIR / name / "models.py").exists() or (MODULES_DIR / name / "models" / "__init__.py").exists()


def test_there_are_modules():
    assert _modules(), "app/modules/ holds no package — the test would pass vacuously"


@pytest.mark.parametrize("name", _modules())
def test_every_module_is_a_regular_package(name):
    assert (MODULES_DIR / name / "__init__.py").exists(), (
        f"app/modules/{name}/ has no __init__.py — it is invisible to every other module check "
        "(R1, R6, the alembic registry, the main.py import) and to import-linter's graph builder"
    )


@pytest.mark.parametrize("name", _modules())
def test_module_has_an_r1_contract_naming_every_other_module(name):
    matches = [
        c for c in _contracts() if c["type"] == "forbidden" and c.get("source_modules") == [f"app.modules.{name}"]
    ]
    assert len(matches) == 1, (
        f"pyproject.toml needs exactly one R1 forbidden contract with source_modules = ['app.modules.{name}']"
    )
    expected = {f"app.modules.{other}.*" for other in _modules() if other != name}
    assert set(matches[0]["forbidden_modules"]) == expected, (
        f"the R1 contract for {name} must forbid exactly {sorted(expected)}"
    )
    assert matches[0].get("allow_indirect_imports") is True, (
        f"the R1 contract for {name} needs allow_indirect_imports = true"
    )


@pytest.mark.parametrize("name", _modules())
def test_module_is_placed_in_the_r6_dag(name):
    r6 = next((c for c in _contracts() if c["name"].startswith("R6")), None)
    assert r6 is not None, (
        "pyproject.toml's [tool.importlinter] table needs a layers contract whose name starts with 'R6'"
    )
    placed = {token.strip() for layer in r6["layers"] for token in layer.split("|")}
    assert f"app.modules.{name}" in placed, f"add app.modules.{name} to the R6 layers in pyproject.toml"


@pytest.mark.parametrize("name", [m for m in _modules() if _has_models_slot(m)])
def test_models_slot_is_imported_by_alembic_env(name):
    tree = ast.parse((SERVER / "alembic" / "env.py").read_text())
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    assert f"app.modules.{name}.models" in imported, f"alembic/env.py must `import app.modules.{name}.models`"


def test_main_imports_every_module_explicitly():
    tree = ast.parse((SERVER / "app" / "main.py").read_text())
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "app.modules"
        for alias in node.names
    }
    missing = sorted(set(_modules()) - imported)
    assert not missing, (
        f"module(s) {missing} have no `from app.modules import <name>` line in app/main.py; "
        "add one so their event subscribers register even without a router"
    )
