import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]


def test_dockerfile_injects_version_before_project_install() -> None:
    lines = (ROOT / "Dockerfile").read_text().splitlines()

    arg_index = lines.index("ARG VERSION")
    copy_index = lines.index("COPY . /app")
    rewrite_index = next(i for i, line in enumerate(lines) if "sed -i" in line)
    install_indices = [
        i for i, line in enumerate(lines) if "uv sync" in line and "--no-dev" in line
    ]

    assert arg_index < copy_index < rewrite_index < install_indices[-1]
    assert 'fallback-version = \\"$VERSION\\"' in lines[rewrite_index]


@pytest.mark.parametrize("fallback", ["0.0.0", "0.24.0b1"])
@pytest.mark.parametrize(
    ("release_version", "python_version"),
    [("0.24.0", "0.24.0"), ("0.24.0-beta.2", "0.24.0b2"), ("0.24.0-rc.1", "0.24.0rc1")],
)
def test_docker_version_rewrite_accepts_existing_release(
    fallback: str, release_version: str, python_version: str, tmp_path: Path
) -> None:
    """Docker normalizes SemVer before replacing any existing Python fallback."""
    dockerfile = (ROOT / "Dockerfile").read_text()
    match = re.search(r"RUN (if .*?fi)", dockerfile, flags=re.DOTALL)
    assert match is not None
    command = match.group(1).replace("\\\n", "")
    command = command.replace("/app/.venv/bin/python", shlex.quote(sys.executable))
    # macOS sed requires a backup suffix for -i; retain the same expression.
    command = command.replace("sed -i ", "sed -i.bak ")
    config = tmp_path / "pyproject.toml"
    config.write_text(f'fallback-version = "{fallback}"\n')
    subprocess.run(
        ["sh", "-c", command],
        cwd=tmp_path,
        env={**os.environ, "VERSION": release_version},
        text=True,
        capture_output=True,
        check=True,
    )
    assert config.read_text() == f'fallback-version = "{python_version}"\n'


def test_docker_workflow_passes_version_and_guards_manual_tag() -> None:
    workflow = (ROOT / ".github" / "workflows" / "docker-publish.yml").read_text()

    assert "VERSION=${{ steps.meta.outputs.version }}" in workflow
    assert (
        "github.event_name == 'workflow_dispatch' && github.ref_type == 'branch'"
    ) in workflow
