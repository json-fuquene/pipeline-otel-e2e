locals {
  log_options = {
    "awslogs-group"         = var.log_group_name
    "awslogs-region"        = var.aws_region
    "awslogs-stream-prefix" = "ecs"
  }
}

resource "aws_ecs_cluster" "lab" {
  name = var.name
}

resource "aws_ecs_task_definition" "lab" {
  family                   = var.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "3072"
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name              = "postgres", image = "${var.ecr_urls["postgres"]}:${var.image_tag}", essential = true,
      memoryReservation = 384,
      portMappings      = [{ containerPort = 5432, hostPort = 5432, protocol = "tcp" }],
      environment       = [{ name = "POSTGRES_USER", value = "postgres" }, { name = "POSTGRES_DB", value = "pipeline" }],
      secrets           = [for key in ["POSTGRES_PASSWORD", "CATALOG_DB_PASSWORD", "ORDERS_DB_PASSWORD"] : { name = key, valueFrom = "${var.database_secret_arn}:${key}::" }],
      healthCheck       = { command = ["CMD-SHELL", "pg_isready -h 127.0.0.1 -U postgres -d pipeline"], interval = 5, timeout = 3, retries = 10, startPeriod = 15 },
      logConfiguration  = { logDriver = "awslogs", options = local.log_options }
    },
    {
      name             = "catalog-migrate", image = "${var.ecr_urls["catalog"]}:${var.image_tag}", essential = false, memoryReservation = 128,
      command          = ["alembic", "-c", "services/catalog/alembic.ini", "upgrade", "head"],
      dependsOn        = [{ containerName = "postgres", condition = "HEALTHY" }],
      environment      = [{ name = "DB_HOST", value = "127.0.0.1" }, { name = "DB_PORT", value = "5432" }, { name = "DB_NAME", value = "pipeline" }, { name = "DB_USER", value = "catalog_app" }],
      secrets          = [{ name = "DB_PASSWORD", valueFrom = "${var.database_secret_arn}:CATALOG_DB_PASSWORD::" }],
      logConfiguration = { logDriver = "awslogs", options = local.log_options }
    },
    {
      name             = "orders-migrate", image = "${var.ecr_urls["orders"]}:${var.image_tag}", essential = false, memoryReservation = 128,
      command          = ["alembic", "-c", "services/orders/alembic.ini", "upgrade", "head"],
      dependsOn        = [{ containerName = "postgres", condition = "HEALTHY" }],
      environment      = [{ name = "DB_HOST", value = "127.0.0.1" }, { name = "DB_PORT", value = "5432" }, { name = "DB_NAME", value = "pipeline" }, { name = "DB_USER", value = "orders_app" }],
      secrets          = [{ name = "DB_PASSWORD", valueFrom = "${var.database_secret_arn}:ORDERS_DB_PASSWORD::" }],
      logConfiguration = { logDriver = "awslogs", options = local.log_options }
    },
    {
      name         = "catalog", image = "${var.ecr_urls["catalog"]}:${var.image_tag}", essential = true, memoryReservation = 128,
      command      = ["uvicorn", "services.catalog.app.main:app", "--host", "0.0.0.0", "--port", "8001", "--no-access-log"],
      portMappings = [{ containerPort = 8001, hostPort = 8001, protocol = "tcp" }, { containerPort = 9464, hostPort = 9464, protocol = "tcp" }],
      environment = [
        { name = "DB_HOST", value = "127.0.0.1" }, { name = "DB_PORT", value = "5432" }, { name = "DB_NAME", value = "pipeline" }, { name = "DB_USER", value = "catalog_app" },
        { name = "DEPLOYMENT_ENVIRONMENT", value = "ecs-test" }, { name = "OTEL_EXPORTER_OTLP_ENDPOINT", value = "http://127.0.0.1:4317" }, { name = "OTEL_METRICS_PORT", value = "9464" }, { name = "OTEL_SEMCONV_STABILITY_OPT_IN", value = "http" }, { name = "AWS_REGION", value = var.aws_region }
      ],
      secrets          = [{ name = "DB_PASSWORD", valueFrom = "${var.database_secret_arn}:CATALOG_DB_PASSWORD::" }],
      dependsOn        = [{ containerName = "postgres", condition = "HEALTHY" }, { containerName = "catalog-migrate", condition = "SUCCESS" }],
      healthCheck      = { command = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health/ready', timeout=5)\""], interval = 10, timeout = 6, retries = 5, startPeriod = 30 },
      logConfiguration = { logDriver = "awslogs", options = local.log_options }
    },
    {
      name         = "orders", image = "${var.ecr_urls["orders"]}:${var.image_tag}", essential = true, memoryReservation = 128,
      command      = ["uvicorn", "services.orders.app.main:app", "--host", "0.0.0.0", "--port", "8002", "--no-access-log"],
      portMappings = [{ containerPort = 8002, hostPort = 8002, protocol = "tcp" }, { containerPort = 9465, hostPort = 9465, protocol = "tcp" }],
      environment = [
        { name = "DB_HOST", value = "127.0.0.1" }, { name = "DB_PORT", value = "5432" }, { name = "DB_NAME", value = "pipeline" }, { name = "DB_USER", value = "orders_app" }, { name = "CATALOG_BASE_URL", value = "http://127.0.0.1:8001" },
        { name = "DEPLOYMENT_ENVIRONMENT", value = "ecs-test" }, { name = "OTEL_EXPORTER_OTLP_ENDPOINT", value = "http://127.0.0.1:4317" }, { name = "OTEL_METRICS_PORT", value = "9465" }, { name = "OTEL_SEMCONV_STABILITY_OPT_IN", value = "http" }, { name = "AWS_REGION", value = var.aws_region }
      ],
      secrets          = [{ name = "DB_PASSWORD", valueFrom = "${var.database_secret_arn}:ORDERS_DB_PASSWORD::" }],
      dependsOn        = [{ containerName = "postgres", condition = "HEALTHY" }, { containerName = "orders-migrate", condition = "SUCCESS" }, { containerName = "catalog", condition = "HEALTHY" }],
      healthCheck      = { command = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/health/ready', timeout=5)\""], interval = 10, timeout = 6, retries = 5, startPeriod = 30 },
      logConfiguration = { logDriver = "awslogs", options = local.log_options }
    },
    {
      name             = "jaeger", image = "${var.ecr_urls["jaeger"]}:${var.image_tag}", essential = true, memoryReservation = 384,
      command          = ["--config", "/etc/jaeger/config.yaml"],
      portMappings     = [{ containerPort = 16686, hostPort = 16686, protocol = "tcp" }],
      dependsOn        = [{ containerName = "orders", condition = "START" }],
      logConfiguration = { logDriver = "awslogs", options = local.log_options }
    },
    {
      name             = "otel-collector", image = "${var.ecr_urls["otel-collector"]}:${var.image_tag}", essential = true, memoryReservation = 256,
      command          = ["--config=/etc/otelcol-contrib/config.yaml"],
      portMappings     = [{ containerPort = 4317, hostPort = 4317, protocol = "tcp" }, { containerPort = 4318, hostPort = 4318, protocol = "tcp" }, { containerPort = 8889, hostPort = 8889, protocol = "tcp" }, { containerPort = 13133, hostPort = 13133, protocol = "tcp" }],
      environment      = [{ name = "AWS_REGION", value = var.aws_region }],
      dependsOn        = [{ containerName = "jaeger", condition = "START" }],
      logConfiguration = { logDriver = "awslogs", options = local.log_options }
    },
    {
      name             = "prometheus", image = "${var.ecr_urls["prometheus"]}:${var.image_tag}", essential = true, memoryReservation = 256,
      portMappings     = [{ containerPort = 9090, hostPort = 9090, protocol = "tcp" }],
      dependsOn        = [{ containerName = "otel-collector", condition = "START" }],
      logConfiguration = { logDriver = "awslogs", options = local.log_options }
    },
    {
      name             = "grafana", image = "${var.ecr_urls["grafana"]}:${var.image_tag}", essential = true, memoryReservation = 384,
      portMappings     = [{ containerPort = 3000, hostPort = 3000, protocol = "tcp" }],
      environment      = [{ name = "GF_SECURITY_ADMIN_USER", value = "admin" }, { name = "GF_AUTH_ANONYMOUS_ENABLED", value = "false" }, { name = "GF_USERS_ALLOW_SIGN_UP", value = "false" }, { name = "AWS_REGION", value = var.aws_region }],
      secrets          = [{ name = "GF_SECURITY_ADMIN_PASSWORD", valueFrom = var.grafana_secret_arn }],
      dependsOn        = [{ containerName = "prometheus", condition = "START" }, { containerName = "jaeger", condition = "START" }],
      logConfiguration = { logDriver = "awslogs", options = local.log_options }
    }
  ])
}

resource "aws_ecs_service" "lab" {
  name            = var.name
  cluster         = aws_ecs_cluster.lab.id
  task_definition = aws_ecs_task_definition.lab.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [var.security_group_id]
    assign_public_ip = true
  }
}
