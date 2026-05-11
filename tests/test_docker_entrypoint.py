import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_docker_entrypoint_has_valid_shell_syntax() -> None:
    subprocess.run(
        ["sh", "-n", str(REPO_ROOT / "docker" / "entrypoint.sh")],
        check=True,
    )


def test_dockerfile_uses_entrypoint_to_drop_privileges() -> None:
    dockerfile = (REPO_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")

    assert "gosu" in dockerfile
    assert 'ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]' in dockerfile
    assert "USER dsa" not in dockerfile


def test_docker_entrypoint_repairs_ownership_and_user_permissions() -> None:
    entrypoint = (REPO_ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")

    assert 'chown -R "$APP_UID:$APP_GID" "$dir"' in entrypoint
    assert 'chmod -R u+rwX "$dir"' in entrypoint
