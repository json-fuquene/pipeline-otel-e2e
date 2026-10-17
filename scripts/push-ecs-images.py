#!/usr/bin/env python3
"""Build and publish the pinned ECS test images to Terraform-created ECR repos."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

# ID-002: laboratorio de una tarea (infra/otel-ecs-lab).
LAB_IMAGES = {
    "catalog": "services/catalog/Dockerfile",
    "orders": "services/orders/Dockerfile",
    "postgres": "docker/postgres/Dockerfile",
    "otel-collector": "docker/otel-collector/Dockerfile",
    "jaeger": "docker/jaeger/Dockerfile",
    "prometheus": "docker/prometheus/Dockerfile",
    "grafana": "docker/grafana/Dockerfile",
}

# ID-003: sistema observable con tres microservicios (infra/aws-observable).
OBSERVABLE_IMAGES = {
    "catalog": "services/catalog/Dockerfile",
    "orders": "services/orders/Dockerfile",
    "data": "services/data/Dockerfile",
    "postgres": "docker/postgres/Dockerfile",
    "otel-collector": "docker/otel-collector/Dockerfile.observable",
    "jaeger": "docker/jaeger/Dockerfile",
    "prometheus": "docker/prometheus/Dockerfile.observable",
    "grafana": "docker/grafana/Dockerfile.observable",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Construye y publica imágenes en ECR con tag inmutable.")
    parser.add_argument("region")
    parser.add_argument("urls_path", help="JSON de terraform output -json ecr_urls")
    parser.add_argument("image_tag", nargs="?", default="phase2-test")
    parser.add_argument("--profile", choices=["lab", "observable"], default="lab",
                        help="lab = ID-002 (otel-ecs-lab); observable = ID-003 (aws-observable)")
    args = parser.parse_args()
    region, urls_path, image_tag = args.region, args.urls_path, args.image_tag
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
    image_definitions = OBSERVABLE_IMAGES if args.profile == "observable" else LAB_IMAGES

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
