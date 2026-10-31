from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import commit_all, init_repo
from helpers import check, findings

CONTRACT = """
version = 1
allowed_paths = ["**"]
allowed_dependencies = ["left-pad"]
"""


def _repo(tmp_path: Path, base: dict[str, Any]) -> Path:
    repo = init_repo(tmp_path / "r")
    (repo / "package.json").write_text(json.dumps(base, indent=2) + "\n")
    commit_all(repo)
    (tmp_path / "c.toml").write_text(CONTRACT)
    return repo


BASE: dict[str, Any] = {
    "name": "x",
    "scripts": {"test": "vitest"},
    "dependencies": {"@scope/a": "workspace:*", "@scope/b": "workspace:*", "react": "^19"},
}


def test_allowed_addition_anywhere_is_clean(tmp_path: Path) -> None:
    repo = _repo(tmp_path, BASE)
    head = json.loads(json.dumps(BASE))
    head["dependencies"] = {"@scope/a": "workspace:*", "left-pad": "1", "@scope/b": "workspace:*", "react": "^19"}
    (repo / "package.json").write_text(json.dumps(head, indent=2) + "\n")
    code, report = check(repo, tmp_path / "c.toml", tmp_path / "out")
    assert report["findings"] == [] and code == 3


def test_reorder_detected_with_moved_keys(tmp_path: Path) -> None:
    repo = _repo(tmp_path, BASE)
    head = json.loads(json.dumps(BASE))
    head["dependencies"] = {"left-pad": "1", "react": "^19", "@scope/a": "workspace:*", "@scope/b": "workspace:*"}
    (repo / "package.json").write_text(json.dumps(head, indent=2) + "\n")
    code, report = check(repo, tmp_path / "c.toml", tmp_path / "out")
    assert code == 1
    [hit] = findings(report, "package-json-reorder")
    assert hit["evidence"] == "dependencies: react"


def test_top_level_reorder_detected(tmp_path: Path) -> None:
    repo = _repo(tmp_path, BASE)
    head = {"dependencies": BASE["dependencies"], "name": "x", "scripts": BASE["scripts"]}
    (repo / "package.json").write_text(json.dumps(head, indent=2) + "\n")
    _, report = check(repo, tmp_path / "c.toml", tmp_path / "out")
    assert findings(report, "package-json-reorder")[0]["evidence"].startswith("<root>")


def test_unlisted_dependency_and_version_change(tmp_path: Path) -> None:
    repo = _repo(tmp_path, BASE)
    head = json.loads(json.dumps(BASE))
    head["dependencies"]["react"] = "^18"
    head["devDependencies"] = {"lodash": "4"}
    (repo / "package.json").write_text(json.dumps(head, indent=2) + "\n")
    _, report = check(repo, tmp_path / "c.toml", tmp_path / "out")
    assert [f["evidence"] for f in findings(report, "dependency-not-allowed")] == ['"lodash": "4"']
    assert findings(report, "dependency-changed")


def test_go_mod_new_module(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "g")
    (repo / "go.mod").write_text("module example.com/x\n\ngo 1.22\n\nrequire (\n\tgithub.com/a/b v1.0.0\n)\n")
    commit_all(repo)
    (repo / "go.mod").write_text(
        "module example.com/x\n\ngo 1.22\n\nrequire (\n\tgithub.com/a/b v1.0.0\n"
        "\tgithub.com/evil/dep v0.1.0 // indirect\n\tleft-pad v1.0.0\n)\n"
    )
    (tmp_path / "c.toml").write_text(CONTRACT)
    _, report = check(repo, tmp_path / "c.toml", tmp_path / "out")
    assert [f["message"].split("'")[1] for f in findings(report, "dependency-not-allowed")] == ["github.com/evil/dep"]


@pytest.mark.parametrize(
    "spec",
    [
        "git+https://evil.example/x.git",
        "https://evil.example/x.tgz",
        "file:../x",
        "link:../x",
        "github:u/r",
        "http://x",
        "npm:evil-pkg@1.0.0",
        "NPM:evil-pkg",
        "jsr:@evil/x",
        "patch:left-pad@1#./p.patch",
        "exec:./gen.js",
    ],
)
def test_allowed_dependency_from_non_registry_source(tmp_path: Path, spec: str) -> None:
    repo = _repo(tmp_path, BASE)
    head = json.loads(json.dumps(BASE))
    head["dependencies"]["left-pad"] = spec
    (repo / "package.json").write_text(json.dumps(head, indent=2) + "\n")
    code, report = check(repo, tmp_path / "c.toml", tmp_path / "out")
    assert code == 1 and findings(report, "dependency-source")


def test_go_mod_replace_is_a_finding(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "r")
    (repo / "go.mod").write_text("module x\n\ngo 1.22\n\nreplace a.b/c => a.b/c v1.0.0\n")
    commit_all(repo)
    (repo / "go.mod").write_text(
        "module x\n\ngo 1.22\n\nreplace a.b/c => a.b/c v1.0.0\n\nreplace (\n\tgithub.com/x/y => ../y\n)\n"
        "replace golang.org/z v1.2.0 => example.com/fork/z v1.2.1\n"
    )
    (tmp_path / "c.toml").write_text(CONTRACT)
    code, report = check(repo, tmp_path / "c.toml", tmp_path / "out")
    assert code == 1
    assert sorted(f["evidence"] for f in findings(report, "go-mod-replace")) == [
        "github.com/x/y => ../y",
        "golang.org/z v1.2.0 => example.com/fork/z v1.2.1",
    ]


def test_go_mod_tab_separated_blocks(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "r")
    (repo / "go.mod").write_text("module x\n\ngo 1.22\n")
    commit_all(repo)
    (repo / "go.mod").write_text(
        "module x\n\ngo 1.22\n\nrequire\t(\n\tgithub.com/evil/dep v0.1.0\n)\n"
        "\nreplace\t(\n\tgithub.com/x/y => ../y\n)\n"
        "require\tgithub.com/evil/two v1.0.0\n"
    )
    (tmp_path / "c.toml").write_text(CONTRACT)
    code, report = check(repo, tmp_path / "c.toml", tmp_path / "out")
    assert code == 1
    assert sorted(f["message"].split("'")[1] for f in findings(report, "dependency-not-allowed")) == [
        "github.com/evil/dep",
        "github.com/evil/two",
    ]
    assert [f["evidence"] for f in findings(report, "go-mod-replace")] == ["github.com/x/y => ../y"]


def test_go_mod_only_newline_ends_a_line(tmp_path: Path) -> None:
    # str.splitlines() would split on \x1c and end the block early, hiding the next require line.
    repo = init_repo(tmp_path / "r")
    (repo / "go.mod").write_text("module x\n\ngo 1.22\n")
    commit_all(repo)
    (repo / "go.mod").write_text(
        "module x\n\ngo 1.22\n\nrequire (\n\ta.b/c v1.0.0 // x\x1c)\n\tgithub.com/evil/dep v0.1.0\n)\n"
    )
    (tmp_path / "c.toml").write_text(CONTRACT)
    _, report = check(repo, tmp_path / "c.toml", tmp_path / "out")
    assert "github.com/evil/dep" in " ".join(f["message"] for f in findings(report, "dependency-not-allowed"))


def test_go_work_use_and_replace(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "r")
    (repo / "go.work").write_text("go 1.22\n\nuse ./app\n")
    commit_all(repo)
    (repo / "go.work").write_text("go 1.22\n\nuse ./app\n\nuse\t(\n\t../outside\n)\n\nreplace github.com/x/y => ../y\n")
    (tmp_path / "c.toml").write_text(CONTRACT)
    code, report = check(repo, tmp_path / "c.toml", tmp_path / "out")
    assert code == 1
    assert [f["evidence"] for f in findings(report, "go-work-use")] == ["../outside"]
    assert [f["evidence"] for f in findings(report, "go-mod-replace")] == ["github.com/x/y => ../y"]


@pytest.mark.parametrize("spec", ["^1.2.3", "1.x", ">=1 <2", "latest", "workspace:*"])
def test_registry_specs_are_not_dependency_source(tmp_path: Path, spec: str) -> None:
    repo = _repo(tmp_path, BASE)
    head = json.loads(json.dumps(BASE))
    head["dependencies"]["left-pad"] = spec
    (repo / "package.json").write_text(json.dumps(head, indent=2) + "\n")
    _, report = check(repo, tmp_path / "c.toml", tmp_path / "out")
    assert findings(report, "dependency-source") == []


def test_pyproject_toml_allowed_and_unlisted_dependencies(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "p")
    base_toml = """[project]
name = "demo"
dependencies = [
    "requests>=2.28",
]
"""
    (repo / "pyproject.toml").write_text(base_toml)
    commit_all(repo)

    head_toml = """[project]
name = "demo"
dependencies = [
    "requests>=2.28",
    "left-pad>=1.0",
    "unapproved-pkg==0.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]
"""
    (repo / "pyproject.toml").write_text(head_toml)
    (tmp_path / "c.toml").write_text(CONTRACT)
    code, report = check(repo, tmp_path / "c.toml", tmp_path / "out")
    assert code == 1
    unallowed = sorted(f["message"].split("'")[1] for f in findings(report, "dependency-not-allowed"))
    assert unallowed == ["pytest", "unapproved-pkg"]


def test_pyproject_toml_non_registry_source(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "p")
    (repo / "pyproject.toml").write_text("[project]\nname = 'x'\ndependencies = []\n")
    commit_all(repo)

    (repo / "pyproject.toml").write_text(
        "[project]\nname = 'x'\ndependencies = [\n    'left-pad @ git+https://github.com/example/left-pad.git',\n]\n"
    )
    (tmp_path / "c.toml").write_text(CONTRACT)
    code, report = check(repo, tmp_path / "c.toml", tmp_path / "out")
    assert code == 1
    assert findings(report, "dependency-source")


def test_requirements_txt_unlisted_and_source(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "req")
    (repo / "requirements.txt").write_text("requests==2.31.0\n")
    commit_all(repo)

    (repo / "requirements.txt").write_text(
        "requests==2.31.0\nleft-pad>=1.0\nunapproved-dep==1.0\npkg-tarball @ https://example.com/pkg.whl\n"
    )
    (tmp_path / "c.toml").write_text(CONTRACT)
    code, report = check(repo, tmp_path / "c.toml", tmp_path / "out")
    assert code == 1
    assert "unapproved-dep" in [f["message"].split("'")[1] for f in findings(report, "dependency-not-allowed")]
    assert findings(report, "dependency-source")


