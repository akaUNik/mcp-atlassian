import re
import subprocess
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
def test_docker_version_rewrite_accepts_existing_release(fallback: str) -> None:
    """A Docker tag replaces either an initial or already versioned fallback."""
    dockerfile = (ROOT / "Dockerfile").read_text()
    match = re.search(r'sed -i "(.+)" pyproject.toml', dockerfile)
    assert match is not None
    expression = match.group(1).replace(r"\"", '"').replace("$VERSION", "0.24.0-beta.2")
    result = subprocess.run(
        ["sed", "-e", expression],
        input=f'fallback-version = "{fallback}"\n',
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout == 'fallback-version = "0.24.0-beta.2"\n'


def test_docker_workflow_passes_version_and_guards_manual_tag() -> None:
    workflow = (ROOT / ".github" / "workflows" / "docker-publish.yml").read_text()

    assert "VERSION=${{ steps.meta.outputs.version }}" in workflow
    assert (
        "github.event_name == 'workflow_dispatch' && github.ref_type == 'branch'"
    ) in workflow
