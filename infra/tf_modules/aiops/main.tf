locals {
  namespace = "PipelineOtel/Services"
  # Las rutas de salud se excluyen de los SLIs: las consultan los healthchecks de ECS cada 10 s.
  request_filter = "($.status_code >= 100) && ($.route != \"/health/live\") && ($.route != \"/health/ready\")"
  services       = toset(keys(var.latency_slo_ms))
}

# ---------------------------------------------------------------------------
# SLIs derivados de los logs OTel (pilar logs → métricas CloudWatch con percentiles)
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_metric_filter" "requests" {
  name           = "${var.name}-requests"
  log_group_name = var.otel_log_group_name
  pattern        = "{ ${local.request_filter} }"
  metric_transformation {
    name       = "RequestCount"
    namespace  = local.namespace
    value      = "1"
    unit       = "Count"
    dimensions = { service = "$.service" }
  }
}

resource "aws_cloudwatch_log_metric_filter" "server_errors" {
  name           = "${var.name}-server-errors"
  log_group_name = var.otel_log_group_name
  pattern        = "{ ${local.request_filter} && ($.status_code >= 500) }"
  metric_transformation {
    name       = "ServerErrorCount"
    namespace  = local.namespace
    value      = "1"
    unit       = "Count"
    dimensions = { service = "$.service" }
  }
}

resource "aws_cloudwatch_log_metric_filter" "latency" {
  name           = "${var.name}-latency"
  log_group_name = var.otel_log_group_name
  pattern        = "{ ${local.request_filter} }"
  metric_transformation {
    name       = "RequestLatency"
    namespace  = local.namespace
    value      = "$.duration_ms"
    unit       = "Milliseconds"
    dimensions = { service = "$.service" }
  }
}

# ---------------------------------------------------------------------------
# Notificación: tópico crudo → Lambda enriquecedora → tópico enriquecido
# ---------------------------------------------------------------------------
resource "aws_sns_topic" "raw" {
  name = "${var.name}-alarms-raw"
}

resource "aws_sns_topic" "enriched" {
  name = "${var.name}-alerts-enriched"
}

resource "aws_sns_topic" "static" {
  name = "${var.name}-alarms-static"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.enriched.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# En la misma cuenta, DevOps Guru agrega por sí mismo la política del tópico al registrar el canal;
# no se declara aws_sns_topic_policy para no sobrescribirla en cada apply.

# ---------------------------------------------------------------------------
# Alarmas por servicio
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "static_error_rate" {
  for_each            = local.services
  alarm_name          = "${var.name}-${each.key}-static-error-rate"
  alarm_description   = jsonencode({ service = each.key, kind = "error", group = "static", rule = "error_rate > ${var.static_error_rate_pct}%" })
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.static_error_rate_pct
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.static.arn]
  ok_actions          = [aws_sns_topic.static.arn]

  metric_query {
    id = "requests"
    metric {
      namespace   = local.namespace
      metric_name = "RequestCount"
      dimensions  = { service = each.key }
      period      = 60
      stat        = "Sum"
    }
  }
  metric_query {
    id = "errors"
    metric {
      namespace   = local.namespace
      metric_name = "ServerErrorCount"
      dimensions  = { service = each.key }
      period      = 60
      stat        = "Sum"
    }
  }
  metric_query {
    id          = "error_rate"
    expression  = "100 * FILL(errors, 0) / requests"
    label       = "${each.key} error rate (%)"
    return_data = true
  }
  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "latency_slo" {
  for_each            = local.services
  alarm_name          = "${var.name}-${each.key}-p99-slo"
  alarm_description   = jsonencode({ service = each.key, kind = "latency", group = "static", rule = "latency_p99 > ${var.latency_slo_ms[each.key]} ms (SLO)" })
  namespace           = local.namespace
  metric_name         = "RequestLatency"
  dimensions          = { service = each.key }
  extended_statistic  = "p99"
  period              = 60
  comparison_operator = "GreaterThanThreshold"
  threshold           = var.latency_slo_ms[each.key]
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.static.arn]
  ok_actions          = [aws_sns_topic.static.arn]
  tags                = var.tags
}

# Umbral dinámico: banda de detección de anomalías de 2 desviaciones estándar (baseline + 2σ).
resource "aws_cloudwatch_metric_alarm" "error_anomaly" {
  for_each            = local.services
  alarm_name          = "${var.name}-${each.key}-error-anomaly"
  alarm_description   = jsonencode({ service = each.key, kind = "error", group = "aiops-component", rule = "error_rate > baseline + 2σ" })
  comparison_operator = "GreaterThanUpperThreshold"
  threshold_metric_id = "band"
  # Los metric filters publican con ~1 min de retraso: se evalúan 3 periodos y basta 1 fuera de la banda.
  evaluation_periods  = 3
  datapoints_to_alarm = 1
  treat_missing_data  = "notBreaching"

  metric_query {
    id = "requests"
    metric {
      namespace   = local.namespace
      metric_name = "RequestCount"
      dimensions  = { service = each.key }
      period      = 60
      stat        = "Sum"
    }
  }
  metric_query {
    id = "errors"
    metric {
      namespace   = local.namespace
      metric_name = "ServerErrorCount"
      dimensions  = { service = each.key }
      period      = 60
      stat        = "Sum"
    }
  }
  metric_query {
    id          = "error_rate"
    expression  = "100 * FILL(errors, 0) / requests"
    label       = "${each.key} error rate (%)"
    return_data = true
  }
  metric_query {
    id          = "band"
    expression  = "ANOMALY_DETECTION_BAND(error_rate, ${var.anomaly_band_stddev})"
    label       = "error rate expected band"
    return_data = true
  }
  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "latency_anomaly" {
  for_each            = local.services
  alarm_name          = "${var.name}-${each.key}-latency-anomaly"
  alarm_description   = jsonencode({ service = each.key, kind = "latency", group = "aiops-component", rule = "latency_p99 > baseline + 2σ" })
  comparison_operator = "GreaterThanUpperThreshold"
  threshold_metric_id = "band"
  # Los metric filters publican con ~1 min de retraso: se evalúan 3 periodos y basta 1 fuera de la banda.
  evaluation_periods  = 3
  datapoints_to_alarm = 1
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "p99"
    return_data = true
    metric {
      namespace   = local.namespace
      metric_name = "RequestLatency"
      dimensions  = { service = each.key }
      period      = 60
      stat        = "p99"
    }
  }
  metric_query {
    id          = "band"
    expression  = "ANOMALY_DETECTION_BAND(p99, ${var.anomaly_band_stddev})"
    label       = "p99 expected band"
    return_data = true
  }
  tags = var.tags
}

# Regla de correlación del Módulo B: error_rate > baseline + 2σ  Y  latency_p99 > SLO.
resource "aws_cloudwatch_composite_alarm" "correlated_errors" {
  for_each          = local.services
  alarm_name        = "${var.name}-${each.key}-correlated-errors"
  alarm_description = jsonencode({ service = each.key, kind = "correlated", group = "aiops", rule = "error_rate > baseline + 2σ AND latency_p99 > SLO" })
  alarm_rule        = "ALARM(\"${aws_cloudwatch_metric_alarm.error_anomaly[each.key].alarm_name}\") AND ALARM(\"${aws_cloudwatch_metric_alarm.latency_slo[each.key].alarm_name}\")"
  alarm_actions     = [aws_sns_topic.raw.arn]
  ok_actions        = [aws_sns_topic.raw.arn]
  tags              = var.tags
}

# Degradación de latencia: el SLO se viola Y el p99 sale de su banda esperada.
resource "aws_cloudwatch_composite_alarm" "latency_degradation" {
  for_each          = local.services
  alarm_name        = "${var.name}-${each.key}-latency-degradation"
  alarm_description = jsonencode({ service = each.key, kind = "latency", group = "aiops", rule = "latency_p99 > SLO AND latency_p99 > baseline + 2σ" })
  alarm_rule        = "ALARM(\"${aws_cloudwatch_metric_alarm.latency_slo[each.key].alarm_name}\") AND ALARM(\"${aws_cloudwatch_metric_alarm.latency_anomaly[each.key].alarm_name}\")"
  alarm_actions     = [aws_sns_topic.raw.arn]
  ok_actions        = [aws_sns_topic.raw.arn]
  tags              = var.tags
}

# ---------------------------------------------------------------------------
# Lambda que enriquece cada alerta con trace_id, consultas y runbook
# ---------------------------------------------------------------------------
data "archive_file" "enricher" {
  type        = "zip"
  source_file = "${var.lambda_source_dir}/alert_enricher/handler.py"
  output_path = "${path.module}/.build/alert_enricher.zip"
}

resource "aws_cloudwatch_log_group" "enricher" {
  name              = "/aws/lambda/${var.name}-alert-enricher"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "enricher" {
  name = "${var.name}-alert-enricher"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "enricher" {
  name = "enrich-alerts"
  role = aws_iam_role.enricher.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.enricher.arn}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:StartQuery"]
        Resource = concat([var.otel_log_group_arn], var.extra_query_log_group_arns)
      },
      {
        Effect   = "Allow"
        Action   = ["logs:GetQueryResults", "logs:StopQuery"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = aws_sns_topic.enriched.arn
      },
      {
        Effect    = "Allow"
        Action    = ["cloudwatch:PutMetricData"]
        Resource  = "*"
        Condition = { StringEquals = { "cloudwatch:namespace" = "PipelineOtel/AIOps" } }
      },
      {
        Effect   = "Allow"
        Action   = ["cloudwatch:GetMetricData"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_lambda_function" "enricher" {
  function_name    = "${var.name}-alert-enricher"
  role             = aws_iam_role.enricher.arn
  runtime          = "python3.13"
  handler          = "handler.handler"
  filename         = data.archive_file.enricher.output_path
  source_code_hash = data.archive_file.enricher.output_base64sha256
  timeout          = 60
  memory_size      = 256
  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.enricher.name
  }
  environment {
    variables = {
      OTEL_LOG_GROUP     = var.otel_log_group_name
      FLOW_LOG_GROUP     = var.flow_log_group_name
      FINDINGS_LOG_GROUP = var.findings_log_group_name
      ECS_LOG_GROUP      = var.ecs_log_group_name
      VPC_CIDR           = var.vpc_cidr
      ENRICHED_TOPIC_ARN = aws_sns_topic.enriched.arn
      LAB_NAME           = var.name
      LATENCY_SLO_MS     = jsonencode(var.latency_slo_ms)
      GRAFANA_HINT       = "Grafana > Explore > Jaeger (TraceID) o Jaeger UI :16686/trace/<trace_id>"
    }
  }
  tags = var.tags
}

resource "aws_lambda_permission" "sns" {
  statement_id  = "AllowRawAlarmTopic"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.enricher.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.raw.arn
}

resource "aws_sns_topic_subscription" "enricher" {
  topic_arn = aws_sns_topic.raw.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.enricher.arn
}

# ---------------------------------------------------------------------------
# AWS DevOps Guru sobre la frontera data-service + RDS (por etiqueta)
# ---------------------------------------------------------------------------
resource "aws_devopsguru_resource_collection" "data_service" {
  count = var.enable_devops_guru ? 1 : 0
  type  = "AWS_TAGS"
  tags {
    app_boundary_key = var.devops_guru_tag_key
    tag_values       = [var.devops_guru_tag_value]
  }
}

resource "aws_devopsguru_notification_channel" "enriched" {
  count = var.enable_devops_guru ? 1 : 0
  sns {
    topic_arn = aws_sns_topic.enriched.arn
  }
  filters {
    message_types = ["NEW_INSIGHT", "CLOSED_INSIGHT", "SEVERITY_UPGRADED"]
    severities    = ["LOW", "MEDIUM", "HIGH"]
  }
}
