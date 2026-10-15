locals { log_group = var.log_group_name }

resource "random_password" "database" {
  for_each         = toset(["postgres", "catalog", "orders"])
  length           = 32
  special          = false
  override_special = ""
}

resource "aws_secretsmanager_secret" "database" {
  name                    = "${var.name}/database"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "database" {
  secret_id = aws_secretsmanager_secret.database.id
  secret_string = jsonencode({
    POSTGRES_PASSWORD   = random_password.database["postgres"].result
    CATALOG_DB_PASSWORD = random_password.database["catalog"].result
    ORDERS_DB_PASSWORD  = random_password.database["orders"].result
  })
}

resource "random_password" "grafana" {
  length           = 32
  special          = false
  override_special = ""
}

resource "aws_secretsmanager_secret" "grafana" {
  name                    = var.grafana_secret_name
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "grafana" {
  secret_id     = aws_secretsmanager_secret.grafana.id
  secret_string = random_password.grafana.result
}

resource "aws_cloudwatch_log_group" "ecs" {
  name              = var.log_group_name
  retention_in_days = 1
}

resource "aws_cloudwatch_log_group" "otel" {
  name              = var.otel_log_group_name
  retention_in_days = 1
}

resource "aws_iam_role" "execution" {
  name = "${var.name}-execution"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secret" {
  name = "read-lab-secret"
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [aws_secretsmanager_secret.database.arn, aws_secretsmanager_secret.grafana.arn]
    }]
  })
}

resource "aws_iam_role" "task" {
  name               = "${var.name}-task"
  assume_role_policy = aws_iam_role.execution.assume_role_policy
}

resource "aws_iam_role_policy" "task_logs" {
  name = "write-otel-cloudwatch-logs"
  role = aws_iam_role.task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams", "logs:PutRetentionPolicy"]
      Resource = "${aws_cloudwatch_log_group.otel.arn}:*"
    }]
  })
}

resource "aws_iam_role_policy" "grafana_cloudwatch_read" {
  name = "grafana-cloudwatch-read"
  role = aws_iam_role.task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["cloudwatch:GetMetricData", "cloudwatch:GetMetricStatistics", "cloudwatch:ListMetrics"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:DescribeLogGroups"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:DescribeLogStreams",
          "logs:FilterLogEvents",
          "logs:GetLogEvents",
          "logs:GetLogGroupFields"
        ]
        Resource = [
          "${aws_cloudwatch_log_group.ecs.arn}:*",
          "${aws_cloudwatch_log_group.otel.arn}:*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:StartQuery"]
        Resource = [aws_cloudwatch_log_group.ecs.arn, aws_cloudwatch_log_group.otel.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:GetQueryResults", "logs:StopQuery"]
        Resource = "*"
      }
    ]
  })
}
