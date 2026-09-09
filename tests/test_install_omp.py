import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def installation(tmp_path):
    repo = tmp_path / "repo with spaces"
    home = tmp_path / "home"
    binaries = tmp_path / "bin"
    for directory in (repo / "scripts", repo / "docs/oh-my-pi", home, binaries):
        directory.mkdir(parents=True)
    source = ROOT / "scripts/install-omp.sh"
    if source.exists():
        shutil.copy(source, repo / "scripts/install-omp.sh")
    shutil.copy(ROOT / "docs/oh-my-pi/models.yml", repo / "docs/oh-my-pi/models.yml")
    (repo / ".gitignore").write_text(".env\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for name in ("omp", "curl", "ollama"):
        executable = binaries / name
        executable.write_text('#!/bin/sh\nprintf "%s\\n" "$0 $*" >> "$CALLS"\n')
        executable.chmod(0o755)
    environment = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{binaries}:/usr/bin:/bin",
        "CALLS": str(tmp_path / "calls"),
    }
    for name in ("PI_CODING_AGENT_DIR", "OMP_CODING_AGENT_DIR", "OPENROUTER_API_KEY"):
        environment.pop(name, None)
    return repo, home, environment


def run_installer(installation, answers="", *arguments):
    repo, _, environment = installation
    return subprocess.run(
        ["bash", str(repo / "scripts/install-omp.sh"), *arguments],
        input=answers,
        text=True,
        capture_output=True,
        env=environment,
        timeout=15,
    )


def test_dry_run_has_no_writes_or_external_commands(installation):
    repo, home, environment = installation
    result = run_installer(installation, "", "--dry")
    assert result.returncode == 0, result.stderr
    assert "DRY RUN" in result.stdout
    assert not list(home.iterdir())
    assert not (repo / ".env").exists()
    assert not Path(environment["CALLS"]).exists()


def test_keys_are_private_and_existing_env_values_survive(installation):
    repo, home, _ = installation
    (repo / ".env").write_text("OTHER_SETTING=keep\nOPENROUTER_API_KEY=old\n")
    result = run_installer(installation, "1\nrouter-secret\nablit-secret\nn\n")
    assert result.returncode == 0, result.stderr
    target = home / ".omp/agent/models.yml"
    models = yaml.safe_load(target.read_text())["providers"]
    assert models["abliteration"]["apiKey"] == "ablit-secret"
    assert models["openrouter"]["apiKey"] == "OPENROUTER_API_KEY"
    assert "ollama" not in models
    assert (repo / ".env").read_text() == "OTHER_SETTING=keep\nOPENROUTER_API_KEY=router-secret\n"
    assert target.stat().st_mode & 0o777 == 0o600
    assert (repo / ".env").stat().st_mode & 0o777 == 0o600
    assert "secret" not in result.stdout + result.stderr
    backups = list((home / ".omp/agent/backups").iterdir())
    assert len(backups) == 1
    assert backups[0].read_text() == "OTHER_SETTING=keep\nOPENROUTER_API_KEY=old\n"
    assert backups[0].stat().st_mode & 0o777 == 0o600
    assert not list(repo.glob(".env.backup.*"))


def test_literal_key_does_not_write_repository_env(installation):
    repo, home, _ = installation
    result = run_installer(installation, "2\nrouter-secret\n\nn\n")
    assert result.returncode == 0, result.stderr
    models = yaml.safe_load((home / ".omp/agent/models.yml").read_text())["providers"]
    assert models["openrouter"]["apiKey"] == "router-secret"
    assert "abliteration" not in models
    assert not (repo / ".env").exists()


@pytest.mark.parametrize("key", ["$(touch bad)", "key'quote", "key with spaces"])
def test_invalid_keys_fail_before_writing(installation, key):
    repo, home, _ = installation
    result = run_installer(installation, f"1\n{key}\n")
    assert result.returncode != 0
    assert "unsupported characters" in result.stderr
    assert key not in result.stdout + result.stderr
    assert not (home / ".omp").exists()
    assert not (repo / ".env").exists()


def test_declining_replacement_preserves_existing_config(installation):
    _, home, _ = installation
    target = home / ".omp/agent/models.yml"
    target.parent.mkdir(parents=True)
    target.write_text("providers: {}\n")
    result = run_installer(installation, "n\n")
    assert result.returncode == 0, result.stderr
    assert target.read_text() == "providers: {}\n"
    assert list(target.parent.iterdir()) == [target]


def test_symlinked_config_is_rejected(installation):
    repo, home, _ = installation
    target = home / ".omp/agent/models.yml"
    target.parent.mkdir(parents=True)
    original = repo / "original"
    original.write_text("unchanged")
    target.symlink_to(original)
    result = run_installer(installation)
    assert result.returncode != 0
    assert "Refusing a symlink" in result.stderr
    assert original.read_text() == "unchanged"


def test_unignored_env_is_rejected_before_keys_are_written(installation):
    repo, home, _ = installation
    (repo / ".gitignore").write_text("")
    result = run_installer(installation, "1\nrouter-secret\nablit-secret\nn\n")
    assert result.returncode != 0
    assert ".env must be ignored" in result.stderr
    assert not (repo / ".env").exists()
    assert not (home / ".omp").exists()


def test_failed_install_does_not_write_settings(installation):
    repo, home, environment = installation
    binaries = Path(environment["CALLS"]).parent / "bin"
    (binaries / "omp").unlink()
    (binaries / "curl").write_text("#!/bin/sh\nexit 22\n")
    result = run_installer(installation, "2\nrouter-secret\n\ny\n")
    assert result.returncode == 22
    assert not (home / ".omp").exists()
    assert not (repo / ".env").exists()


def test_tracked_env_is_rejected(installation):
    repo, home, _ = installation
    (repo / ".env").write_text("OTHER=keep\n")
    subprocess.run(["git", "-C", str(repo), "add", "-f", ".env"], check=True)
    result = run_installer(installation, "1\nrouter-secret\n")
    assert result.returncode != 0
    assert ".env is tracked" in result.stderr
    assert (repo / ".env").read_text() == "OTHER=keep\n"
    assert not (home / ".omp").exists()


def test_replacement_keeps_recoverable_private_backup(installation):
    _, home, _ = installation
    target = home / ".omp/agent/models.yml"
    target.parent.mkdir(parents=True)
    original = 'providers:\n  personal:\n    apiKey: "old-key"\n'
    target.write_text(original)
    result = run_installer(installation, "y\n3\n\nn\n")
    assert result.returncode == 0, result.stderr
    assert yaml.safe_load(target.read_text()) == {"providers": {}}
    backup = next((target.parent / "backups").iterdir())
    assert backup.read_text() == original
    assert backup.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("answers", ["", "1\n", "3\n"])
def test_interrupted_input_leaves_no_partial_settings(installation, answers):
    repo, home, _ = installation
    result = run_installer(installation, answers)
    assert result.returncode != 0
    assert "Input ended" in result.stderr
    assert not (home / ".omp").exists()
    assert not (repo / ".env").exists()


def test_installer_omits_ollama(installation):
    _, home, environment = installation
    result = run_installer(installation, "2\nrouter-secret\n\nn\n")
    assert result.returncode == 0, result.stderr
    models = yaml.safe_load((home / ".omp/agent/models.yml").read_text())["providers"]
    assert "ollama" not in models
    calls = Path(environment["CALLS"]).read_text()
    assert "/bin/ollama " not in calls
    assert "Ollama" not in result.stdout
