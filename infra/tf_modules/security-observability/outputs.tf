output "findings_log_group_name" { value = aws_cloudwatch_log_group.findings.name }
output "findings_log_group_arn" { value = aws_cloudwatch_log_group.findings.arn }
output "security_metrics_function" { value = aws_lambda_function.security_metrics.function_name }
output "alarm_names" {
  value = {
    high_findings   = aws_cloudwatch_metric_alarm.high_findings.alarm_name
    failed_auth     = aws_cloudwatch_metric_alarm.failed_auth.alarm_name
    rejected_flows  = aws_cloudwatch_metric_alarm.rejected_flows.alarm_name
    east_west_flows = aws_cloudwatch_metric_alarm.east_west_anomaly.alarm_name
  }
}
