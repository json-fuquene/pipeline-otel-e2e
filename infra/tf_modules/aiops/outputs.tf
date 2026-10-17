output "raw_topic_arn" { value = aws_sns_topic.raw.arn }
output "enriched_topic_arn" { value = aws_sns_topic.enriched.arn }
output "static_topic_arn" { value = aws_sns_topic.static.arn }
output "enricher_log_group_name" { value = aws_cloudwatch_log_group.enricher.name }
output "enricher_log_group_arn" { value = aws_cloudwatch_log_group.enricher.arn }
output "alarm_names" {
  value = {
    static_error_rate   = { for key, alarm in aws_cloudwatch_metric_alarm.static_error_rate : key => alarm.alarm_name }
    latency_slo         = { for key, alarm in aws_cloudwatch_metric_alarm.latency_slo : key => alarm.alarm_name }
    error_anomaly       = { for key, alarm in aws_cloudwatch_metric_alarm.error_anomaly : key => alarm.alarm_name }
    latency_anomaly     = { for key, alarm in aws_cloudwatch_metric_alarm.latency_anomaly : key => alarm.alarm_name }
    correlated_errors   = { for key, alarm in aws_cloudwatch_composite_alarm.correlated_errors : key => alarm.alarm_name }
    latency_degradation = { for key, alarm in aws_cloudwatch_composite_alarm.latency_degradation : key => alarm.alarm_name }
  }
}
