#!/usr/bin/env python3
"""Build and publish the pinned ECS test images to Terraform-created ECR repos."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) not in (3, 4):
        print("Uso: push-ecs-images.py REGION ecr_urls.json [IMAGE_TAG]", file=sys.stderr)
        return 2

    region, urls_path = sys.argv[1:3]
    image_tag = sys.argv[3] if len(sys.argv) == 4 else "phase2-test"
    repository_urls = json.loads(Path(urls_path).read_text(encoding="utf-8"))
    root = Path(__file__).resolve().parents[1]
    registry = next(iter(repository_urls.values())).split("/", 1)[0]
    password = subprocess.run(
        ["aws", "ecr", "get-login-password", "--region", region],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    subprocess.run(
        ["docker", "login", "--username", "AWS", "--password-stdin", registry],
        input=password,
        check=True,
        text=True,
    )
    image_definitions = {
        "catalog": "services/catalog/Dockerfile",
        "orders": "services/orders/Dockerfile",
        "postgres": "docker/postgres/Dockerfile",
        "otel-collector": "docker/otel-collector/Dockerfile",
        "jaeger": "docker/jaeger/Dockerfile",
        "prometheus": "docker/prometheus/Dockerfile",
    }

    for name, dockerfile in image_definitions.items():
        image = repository_urls[name] + ":" + image_tag
        subprocess.run(
            ["docker", "build", "--platform", "linux/amd64", "-f", dockerfile, "-t", image, "."],
            cwd=root,
            check=True,
        )
        subprocess.run(["docker", "push", image], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
