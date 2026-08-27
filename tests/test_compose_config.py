from __future__ import annotations

from pathlib import Path

import yaml


def test_compose_langfuse_file_isolation_and_security() -> None:
    compose_path = Path("compose.yaml")
    assert compose_path.is_file()
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    services = data.get("services", {})
    assert "api" in services
    assert "web" in services
    assert "langfuse-server" not in services
    assert "langfuse-postgres" not in services

    langfuse_compose_path = Path("compose.langfuse.yaml")
    assert langfuse_compose_path.is_file()
    lf_data = yaml.safe_load(langfuse_compose_path.read_text(encoding="utf-8"))
    lf_services = lf_data.get("services", {})

    # Verify Langfuse services
    assert "langfuse-server" in lf_services
    server = lf_services["langfuse-server"]
    ports = server.get("ports", [])
    assert len(ports) == 1
    # Must bind to 127.0.0.1 loopback only
    assert ports[0].startswith("127.0.0.1:")

    # Verify Postgres storage service
    assert "langfuse-postgres" in lf_services
    postgres = lf_services["langfuse-postgres"]
    assert "ports" not in postgres or len(postgres["ports"]) == 0

    # Verify persistent volume
    volumes = lf_data.get("volumes", {})
    assert "langfuse-postgres-data" in volumes

