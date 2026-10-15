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
        "grafana": "docker/grafana/Dockerfile",
    }

    try:
        for name, dockerfile in image_definitions.items():
            repository_url = repository_urls[name]
            try:
                subprocess.run(
                    [
                        "aws",
                        "ecr",
                        "describe-images",
                        "--region",
                        region,
                        "--repository-name",
                        repository_url.split("/", 1)[1],
                        "--image-ids",
                        f"imageTag={image_tag}",
                        "--query",
                        "imageDetails[0].imageDigest",
                        "--output",
                        "text",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as error:
                if "ImageNotFoundException" not in error.stderr:
                    raise
            else:
                print(f"Se omite {name}:{image_tag}; el tag inmutable ya existe en ECR.")
                continue

            image = f"{repository_url}:{image_tag}"
            subprocess.run(
                ["docker", "build", "--platform", "linux/amd64", "-f", dockerfile, "-t", image, "."],
                cwd=root,
                check=True,
            )
            subprocess.run(["docker", "push", image], check=True)
    finally:
        subprocess.run(["docker", "logout", registry], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
