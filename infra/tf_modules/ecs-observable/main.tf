locals {
  log_options = {
    "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
    "awslogs-region"        = var.aws_region
    "awslogs-stream-prefix" = "ecs"
  }

  otlp_endpoint = "http://otel-collector:4317"

  # Tres microservicios. data-service no publica puertos al CIDR: solo recibe tráfico este-oeste.
  apps = {
    catalog = {
      port = 8001, metrics_port = 9464, discovery = "catalog", module = "catalog",
      db_user = "catalog_app", schema = "catalog", secret_key = "CATALOG_DB_PASSWORD", image = "catalog",
      extra_env = []
    }
    orders = {
      port = 8002, metrics_port = 9465, discovery = "orders", module = "orders",
      db_user = "orders_app", schema = "orders", secret_key = "ORDERS_DB_PASSWORD", image = "orders",
      extra_env = [
        { name = "CATALOG_BASE_URL", value = "http://catalog:8001" },
        { name = "DATA_SERVICE_BASE_URL", value = "http://data-service:8003" }
      ]
    }
    data = {
      port = 8003, metrics_port = 9466, discovery = "data-service", module = "data",
      db_user = "data_app", schema = "data", secret_key = "DATA_DB_PASSWORD", image = "data",
      extra_env = [{ name = "DB_CLOUD_PROVIDER", value = "aws" }]
    }
  }

  db_env = [
    { name = "DB_HOST", value = var.db_address },
    { name = "DB_PORT", value = tostring(var.db_port) },
    { name = "DB_NAME", value = var.db_name },
    { name = "DB_SSLMODE", value = "require" }
  ]
}

# ---------------------------------------------------------------------------
# Cluster, namespace de Service Connect y registros
# ---------------------------------------------------------------------------
resource "aws_ecs_cluster" "lab" {
  name = var.name
  setting {
    name  = "containerInsights"
    value = var.container_insights
  }
}

resource "aws_service_discovery_http_namespace" "lab" {
  name        = "${var.name}.local"
  description = "Service Connect namespace for the observable lab (L7 east-west traffic)."
}

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "otel" {
  name              = var.otel_log_group_name
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "service_connect" {
  name              = "/ecs/${var.name}/service-connect"
  retention_in_days = var.log_retention_days
}

# ---------------------------------------------------------------------------
# Secretos: contraseñas de roles de aplicación y administrador de Grafana
# ---------------------------------------------------------------------------
resource "random_password" "app" {
  for_each = local.apps
  length   = 32
  special  = false
}

resource "aws_secretsmanager_secret" "app_db" {
  name                    = "${var.name}/app-database"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "app_db" {
  secret_id     = aws_secretsmanager_secret.app_db.id
  secret_string = jsonencode({ for key, app in local.apps : app.secret_key => random_password.app[key].result })
}

resource "random_password" "grafana" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "grafana" {
  name                    = "${var.name}/grafana"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "grafana" {
  secret_id     = aws_secretsmanager_secret.grafana.id
  secret_string = random_password.grafana.result
}

# Parámetros de caos (Módulo D): las APIs los consultan cada pocos segundos.
resource "aws_ssm_parameter" "chaos" {
  for_each    = local.apps
  name        = "/${var.name}/chaos/${local.apps[each.key].discovery}"
  description = "Chaos experiment configuration for ${local.apps[each.key].discovery}."
  type        = "String"
  value       = jsonencode({ enabled = false })
  lifecycle {
    ignore_changes = [value]
  }
}

# ---------------------------------------------------------------------------
# IAM: rol de ejecución compartido y roles de tarea de privilegio mínimo
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${var.name}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secrets" {
  name = "read-lab-secrets"
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.app_db.arn, aws_secretsmanager_secret.grafana.arn, var.db_master_secret_arn]
    }]
  })
}

resource "aws_iam_role" "app_task" {
  name               = "${var.name}-app-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role_policy" "app_task_chaos" {
  name = "read-chaos-parameters"
  role = aws_iam_role.app_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameter"]
      Resource = [for parameter in aws_ssm_parameter.chaos : parameter.arn]
    }]
  })
}

resource "aws_iam_role" "observability_task" {
  name               = "${var.name}-observability-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role_policy" "collector_logs" {
  name = "collector-write-otel-logs"
  role = aws_iam_role.observability_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
      Resource = "${aws_cloudwatch_log_group.otel.arn}:*"
    }]
  })
}

locals {
  readable_log_groups = concat(
    [aws_cloudwatch_log_group.ecs.arn, aws_cloudwatch_log_group.otel.arn, aws_cloudwatch_log_group.service_connect.arn],
    var.extra_readable_log_group_arns
  )
}

resource "aws_iam_role_policy" "grafana_read" {
  name = "grafana-cloudwatch-read"
  role = aws_iam_role.observability_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["cloudwatch:GetMetricData", "cloudwatch:GetMetricStatistics", "cloudwatch:ListMetrics", "cloudwatch:DescribeAlarms", "cloudwatch:DescribeAlarmHistory"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:DescribeLogGroups", "logs:GetQueryResults", "logs:StopQuery"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:DescribeLogStreams", "logs:FilterLogEvents", "logs:GetLogEvents", "logs:GetLogGroupFields", "logs:StartQuery"]
        Resource = concat(local.readable_log_groups, [for arn in local.readable_log_groups : "${arn}:*"])
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Task definitions de los microservicios
# ---------------------------------------------------------------------------
resource "aws_ecs_task_definition" "app" {
  for_each                 = local.apps
  family                   = "${var.name}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.app_task.arn

  container_definitions = jsonencode([
    {
      name              = "db-bootstrap"
      image             = "${var.ecr_urls["postgres"]}:${var.image_tag}"
      essential         = false
      memoryReservation = 64
      entryPoint        = ["sh", "/usr/local/bin/bootstrap-role.sh"]
      environment = [
        { name = "PGHOST", value = var.db_address },
        { name = "PGPORT", value = tostring(var.db_port) },
        { name = "PGDATABASE", value = var.db_name },
        { name = "PGSSLMODE", value = "require" },
        { name = "BOOTSTRAP_ROLE", value = each.value.db_user },
        { name = "BOOTSTRAP_SCHEMA", value = each.value.schema }
      ]
      secrets = [
        { name = "PGUSER", valueFrom = "${var.db_master_secret_arn}:username::" },
        { name = "PGPASSWORD", valueFrom = "${var.db_master_secret_arn}:password::" },
        { name = "BOOTSTRAP_PASSWORD", valueFrom = "${aws_secretsmanager_secret.app_db.arn}:${each.value.secret_key}::" }
      ]
      logConfiguration = { logDriver = "awslogs", options = local.log_options }
    },
    {
      name              = "migrate"
      image             = "${var.ecr_urls[each.value.image]}:${var.image_tag}"
      essential         = false
      memoryReservation = 128
      command           = ["alembic", "-c", "services/${each.value.module}/alembic.ini", "upgrade", "head"]
      dependsOn         = [{ containerName = "db-bootstrap", condition = "SUCCESS" }]
      environment       = concat(local.db_env, [{ name = "DB_USER", value = each.value.db_user }])
      secrets           = [{ name = "DB_PASSWORD", valueFrom = "${aws_secretsmanager_secret.app_db.arn}:${each.value.secret_key}::" }]
      logConfiguration  = { logDriver = "awslogs", options = local.log_options }
    },
    {
      name              = "app"
      image             = "${var.ecr_urls[each.value.image]}:${var.image_tag}"
      essential         = true
      memoryReservation = 256
      command           = ["uvicorn", "services.${each.value.module}.app.main:app", "--host", "0.0.0.0", "--port", tostring(each.value.port), "--no-access-log"]
      portMappings = [
        { name = "${each.key}-http", containerPort = each.value.port, protocol = "tcp", appProtocol = "http" },
        { name = "${each.key}-metrics", containerPort = each.value.metrics_port, protocol = "tcp", appProtocol = "http" }
      ]
      dependsOn = [{ containerName = "migrate", condition = "SUCCESS" }]
      environment = concat(local.db_env, each.value.extra_env, [
        { name = "DB_USER", value = each.value.db_user },
        { name = "DEPLOYMENT_ENVIRONMENT", value = var.environment },
        { name = "OTEL_EXPORTER_OTLP_ENDPOINT", value = local.otlp_endpoint },
        { name = "OTEL_METRICS_PORT", value = tostring(each.value.metrics_port) },
        { name = "OTEL_SEMCONV_STABILITY_OPT_IN", value = "http,database" },
        { name = "CHAOS_SSM_PARAMETER", value = aws_ssm_parameter.chaos[each.key].name },
        { name = "CHAOS_POLL_SECONDS", value = "5" },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "AWS_DEFAULT_REGION", value = var.aws_region }
      ])
      secrets          = [{ name = "DB_PASSWORD", valueFrom = "${aws_secretsmanager_secret.app_db.arn}:${each.value.secret_key}::" }]
      healthCheck      = { command = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:${each.value.port}/health/live', timeout=5)\""], interval = 10, timeout = 6, retries = 5, startPeriod = 40 }
      logConfiguration = { logDriver = "awslogs", options = local.log_options }
    }
  ])
}

resource "aws_ecs_service" "app" {
  for_each               = local.apps
  name                   = "${var.name}-${each.key}"
  cluster                = aws_ecs_cluster.lab.id
  task_definition        = aws_ecs_task_definition.app[each.key].arn
  desired_count          = var.desired_count
  launch_type            = "FARGATE"
  enable_execute_command = false
  propagate_tags         = "SERVICE"
  wait_for_steady_state  = false

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [var.security_group_id]
    assign_public_ip = true
  }

  service_connect_configuration {
    enabled   = true
    namespace = aws_service_discovery_http_namespace.lab.arn

    service {
      port_name      = "${each.key}-http"
      discovery_name = each.value.discovery
      client_alias {
        port     = each.value.port
        dns_name = each.value.discovery
      }
    }

    service {
      port_name      = "${each.key}-metrics"
      discovery_name = "${each.value.discovery}-metrics"
      client_alias {
        port     = each.value.metrics_port
        dns_name = "${each.value.discovery}-metrics"
      }
    }

    log_configuration {
      log_driver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.service_connect.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = each.key
      }
    }
  }

  # data-service y su base forman la frontera de análisis de DevOps Guru (Módulo B).
  tags = each.key == "data" ? merge(var.tags, var.devops_guru_tags) : var.tags

  depends_on = [aws_ecs_service.observability]
}

# ---------------------------------------------------------------------------
# Servicio de observabilidad: Collector, Jaeger, Prometheus y Grafana
# ---------------------------------------------------------------------------
resource "aws_ecs_task_definition" "observability" {
  family                   = "${var.name}-observability"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "3072"
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.observability_task.arn

  container_definitions = jsonencode([
    {
      name              = "jaeger", image = "${var.ecr_urls["jaeger"]}:${var.image_tag}", essential = true, memoryReservation = 512,
      command           = ["--config", "/etc/jaeger/config.yaml"],
      portMappings      = [{ name = "jaeger-ui", containerPort = 16686, protocol = "tcp" }],
      logConfiguration  = { logDriver = "awslogs", options = local.log_options }
    },
    {
      name              = "otel-collector", image = "${var.ecr_urls["otel-collector"]}:${var.image_tag}", essential = true, memoryReservation = 384,
      command           = ["--config=/etc/otelcol-contrib/config.yaml"],
      portMappings = [
        { name = "otlp-grpc", containerPort = 4317, protocol = "tcp", appProtocol = "grpc" },
        { name = "otlp-http", containerPort = 4318, protocol = "tcp", appProtocol = "http" },
        { name = "collector-prom", containerPort = 8889, protocol = "tcp" }
      ],
      environment = [
        { name = "AWS_REGION", value = var.aws_region },
        { name = "OTEL_LOG_GROUP", value = aws_cloudwatch_log_group.otel.name },
        { name = "DEPLOYMENT_ENVIRONMENT", value = var.environment }
      ],
      dependsOn        = [{ containerName = "jaeger", condition = "START" }],
      logConfiguration = { logDriver = "awslogs", options = local.log_options }
    },
    {
      name              = "prometheus", image = "${var.ecr_urls["prometheus"]}:${var.image_tag}", essential = true, memoryReservation = 384,
      portMappings      = [{ name = "prometheus", containerPort = 9090, protocol = "tcp" }],
      dependsOn         = [{ containerName = "otel-collector", condition = "START" }],
      logConfiguration  = { logDriver = "awslogs", options = local.log_options }
    },
    {
      name              = "grafana", image = "${var.ecr_urls["grafana"]}:${var.image_tag}", essential = true, memoryReservation = 384,
      portMappings      = [{ name = "grafana", containerPort = 3000, protocol = "tcp" }],
      environment = [
        { name = "GF_SECURITY_ADMIN_USER", value = "admin" },
        { name = "GF_AUTH_ANONYMOUS_ENABLED", value = "false" },
        { name = "GF_USERS_ALLOW_SIGN_UP", value = "false" },
        { name = "GF_LOG_LEVEL", value = "info" },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "LAB_NAME", value = var.name }
      ],
      secrets          = [{ name = "GF_SECURITY_ADMIN_PASSWORD", valueFrom = aws_secretsmanager_secret.grafana.arn }],
      dependsOn        = [{ containerName = "prometheus", condition = "START" }, { containerName = "jaeger", condition = "START" }],
      logConfiguration = { logDriver = "awslogs", options = local.log_options }
    }
  ])
}

resource "aws_ecs_service" "observability" {
  name                  = "${var.name}-observability"
  cluster               = aws_ecs_cluster.lab.id
  task_definition       = aws_ecs_task_definition.observability.arn
  desired_count         = var.desired_count
  launch_type           = "FARGATE"
  propagate_tags        = "SERVICE"
  wait_for_steady_state = false

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [var.security_group_id]
    assign_public_ip = true
  }

  service_connect_configuration {
    enabled   = true
    namespace = aws_service_discovery_http_namespace.lab.arn
    service {
      port_name      = "otlp-grpc"
      discovery_name = "otel-collector"
      client_alias {
        port     = 4317
        dns_name = "otel-collector"
      }
    }
    log_configuration {
      log_driver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.service_connect.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "observability"
      }
    }
  }

  tags = var.tags
}
