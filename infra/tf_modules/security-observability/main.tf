locals {
  network_namespace  = "PipelineOtel/Network"
  security_namespace = "PipelineOtel/Security"
  # Prefijo /16 de la VPC para clasificar tráfico este-oeste en los filtros de VPC Flow Logs.
  vpc_prefix = join(".", slice(split(".", cidrhost(var.vpc_cidr, 0)), 0, 2))
  flow_fields_prefix = "version, account, eni"
  flow_fields_suffix = "srcport, dstport, protocol, packets, bytes, start, end"
  flow_fields_tail   = "status, pktsrc, pktdst, direction"
}

data "aws_caller_identity" "current" {}

# ---------------------------------------------------------------------------
# Security Hub + estándar FSBP + Amazon Inspector (CVEs de imágenes ECR)
# ---------------------------------------------------------------------------
resource "aws_securityhub_account" "this" {
  count                     = var.enable_security_hub ? 1 : 0
  enable_default_standards  = false
  control_finding_generator = "SECURITY_CONTROL"
  auto_enable_controls      = true
}

resource "aws_securityhub_standards_subscription" "fsbp" {
  count         = var.enable_security_hub ? 1 : 0
  standards_arn = "arn:aws:securityhub:${var.aws_region}::standards/aws-foundational-security-best-practices/v/1.0.0"
  depends_on    = [aws_securityhub_account.this]
}

resource "aws_inspector2_enabler" "ecr" {
  count          = var.enable_inspector ? 1 : 0
  account_ids    = [data.aws_caller_identity.current.account_id]
  resource_types = ["ECR"]
}

resource "aws_guardduty_detector" "this" {
  count  = var.enable_guardduty ? 1 : 0
  enable = true
}

# Hallazgos importados en Security Hub → CloudWatch Logs (consultables desde Grafana).
resource "aws_cloudwatch_log_group" "findings" {
  name              = "/aws/events/${var.name}/security-findings"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "findings_log_policy" {
  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.findings.arn}:*"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com", "delivery.logs.amazonaws.com"]
    }
  }
}

resource "aws_cloudwatch_log_resource_policy" "findings" {
  policy_name     = "${var.name}-security-findings"
  policy_document = data.aws_iam_policy_document.findings_log_policy.json
}

resource "aws_cloudwatch_event_rule" "findings" {
  name        = "${var.name}-securityhub-findings"
  description = "Security Hub findings imported (Inspector CVEs, FSBP controls, GuardDuty)."
  event_pattern = jsonencode({
    source        = ["aws.securityhub"]
    "detail-type" = ["Security Hub Findings - Imported"]
    detail = {
      findings = {
        RecordState = ["ACTIVE"]
        Severity    = { Label = ["CRITICAL", "HIGH", "MEDIUM"] }
      }
    }
  })
}

resource "aws_cloudwatch_event_target" "findings_logs" {
  rule = aws_cloudwatch_event_rule.findings.name
  arn  = aws_cloudwatch_log_group.findings.arn
}

resource "aws_cloudwatch_log_metric_filter" "high_findings" {
  name           = "${var.name}-high-findings"
  log_group_name = aws_cloudwatch_log_group.findings.name
  pattern        = "{ ($.detail.findings[0].Severity.Label = \"HIGH\") || ($.detail.findings[0].Severity.Label = \"CRITICAL\") }"
  metric_transformation {
    name      = "HighSeverityFindings"
    namespace = local.security_namespace
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "high_findings" {
  alarm_name          = "${var.name}-security-high-findings"
  alarm_description   = jsonencode({ service = "account", kind = "security", group = "security", rule = "new HIGH/CRITICAL Security Hub finding" })
  namespace           = local.security_namespace
  metric_name         = "HighSeverityFindings"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.alarm_topic_arn]
  tags                = var.tags
}

# Intentos de autenticación fallidos contra la consola Grafana (única interfaz con login del laboratorio).
resource "aws_cloudwatch_log_metric_filter" "failed_auth" {
  name           = "${var.name}-grafana-failed-auth"
  log_group_name = var.ecs_log_group_name
  pattern        = "?\"invalid username or password\" ?\"Invalid username or password\" ?\"password-auth.failed\""
  metric_transformation {
    name      = "FailedAuthAttempts"
    namespace = local.security_namespace
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "failed_auth" {
  alarm_name          = "${var.name}-security-failed-auth"
  alarm_description   = jsonencode({ service = "grafana", kind = "security", group = "security", rule = "failed logins >= ${var.failed_auth_threshold} in 5 min" })
  namespace           = local.security_namespace
  metric_name         = "FailedAuthAttempts"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.failed_auth_threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.alarm_topic_arn]
  tags                = var.tags
}

# ---------------------------------------------------------------------------
# VPC Flow Logs → métricas de red (N-S / E-W / rechazos) y alertas de tráfico anómalo
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_metric_filter" "rejected_flows" {
  name           = "${var.name}-rejected-flows"
  log_group_name = var.flow_log_group_name
  pattern        = "[${local.flow_fields_prefix}, srcaddr, dstaddr, ${local.flow_fields_suffix}, action=\"REJECT\", ${local.flow_fields_tail}]"
  metric_transformation {
    name      = "RejectedFlows"
    namespace = local.network_namespace
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_log_metric_filter" "accepted_bytes" {
  name           = "${var.name}-accepted-bytes"
  log_group_name = var.flow_log_group_name
  pattern        = "[${local.flow_fields_prefix}, srcaddr, dstaddr, ${local.flow_fields_suffix}, action=\"ACCEPT\", ${local.flow_fields_tail}]"
  metric_transformation {
    name      = "AcceptedBytes"
    namespace = local.network_namespace
    value     = "$bytes"
    unit      = "Bytes"
  }
}

resource "aws_cloudwatch_log_metric_filter" "east_west_bytes" {
  name           = "${var.name}-east-west-bytes"
  log_group_name = var.flow_log_group_name
  pattern        = "[${local.flow_fields_prefix}, srcaddr=\"${local.vpc_prefix}.*\", dstaddr=\"${local.vpc_prefix}.*\", ${local.flow_fields_suffix}, action=\"ACCEPT\", ${local.flow_fields_tail}]"
  metric_transformation {
    name      = "EastWestBytes"
    namespace = local.network_namespace
    value     = "$bytes"
    unit      = "Bytes"
  }
}

resource "aws_cloudwatch_metric_alarm" "rejected_flows" {
  alarm_name          = "${var.name}-network-rejected-flows"
  alarm_description   = jsonencode({ service = "vpc", kind = "network", group = "network", rule = "rejected flows > ${var.rejected_flows_threshold} in 5 min" })
  namespace           = local.network_namespace
  metric_name         = "RejectedFlows"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.rejected_flows_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.alarm_topic_arn]
  ok_actions          = [var.alarm_topic_arn]
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "east_west_anomaly" {
  alarm_name          = "${var.name}-network-east-west-anomaly"
  alarm_description   = jsonencode({ service = "vpc", kind = "network", group = "network", rule = "east-west bytes outside baseline ± 2σ" })
  comparison_operator = "LessThanLowerOrGreaterThanUpperThreshold"
  threshold_metric_id = "band"
  evaluation_periods  = 3
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.alarm_topic_arn]
  ok_actions          = [var.alarm_topic_arn]

  metric_query {
    id          = "ew"
    return_data = true
    metric {
      namespace   = local.network_namespace
      metric_name = "EastWestBytes"
      period      = 60
      stat        = "Sum"
    }
  }
  metric_query {
    id          = "band"
    expression  = "ANOMALY_DETECTION_BAND(ew, 2)"
    label       = "east-west expected band"
    return_data = true
  }
  tags = var.tags
}

# ---------------------------------------------------------------------------
# Lambda programada: hallazgos activos por severidad → PipelineOtel/Security
# ---------------------------------------------------------------------------
data "archive_file" "security_metrics" {
  type        = "zip"
  source_file = "${var.lambda_source_dir}/security_metrics/handler.py"
  output_path = "${path.module}/.build/security_metrics.zip"
}

resource "aws_cloudwatch_log_group" "security_metrics" {
  name              = "/aws/lambda/${var.name}-security-metrics"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "security_metrics" {
  name = "${var.name}-security-metrics"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy" "security_metrics" {
  name = "publish-security-metrics"
  role = aws_iam_role.security_metrics.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.security_metrics.arn}:*" },
      { Effect = "Allow", Action = ["securityhub:GetFindings"], Resource = "*" },
      {
        Effect    = "Allow"
        Action    = ["cloudwatch:PutMetricData"]
        Resource  = "*"
        Condition = { StringEquals = { "cloudwatch:namespace" = local.security_namespace } }
      }
    ]
  })
}

resource "aws_lambda_function" "security_metrics" {
  function_name    = "${var.name}-security-metrics"
  role             = aws_iam_role.security_metrics.arn
  runtime          = "python3.13"
  handler          = "handler.handler"
  filename         = data.archive_file.security_metrics.output_path
  source_code_hash = data.archive_file.security_metrics.output_base64sha256
  timeout          = 60
  memory_size      = 128
  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.security_metrics.name
  }
  tags = var.tags
}

resource "aws_cloudwatch_event_rule" "security_metrics" {
  name                = "${var.name}-security-metrics"
  description         = "Publish active Security Hub findings by severity."
  schedule_expression = "rate(15 minutes)"
}

resource "aws_cloudwatch_event_target" "security_metrics" {
  rule = aws_cloudwatch_event_rule.security_metrics.name
  arn  = aws_lambda_function.security_metrics.arn
}

resource "aws_lambda_permission" "security_metrics" {
  statement_id  = "AllowScheduledInvocation"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.security_metrics.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.security_metrics.arn
}
