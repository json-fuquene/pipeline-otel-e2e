output "cluster_name" { value = aws_ecs_cluster.lab.name }
output "service_names" {
  value = merge({ for key, service in aws_ecs_service.app : key => service.name }, { observability = aws_ecs_service.observability.name })
}
output "discovery_names" { value = { for key, app in local.apps : key => app.discovery } }
output "namespace_name" { value = aws_service_discovery_http_namespace.lab.name }
output "ecs_log_group_name" { value = aws_cloudwatch_log_group.ecs.name }
output "ecs_log_group_arn" { value = aws_cloudwatch_log_group.ecs.arn }
output "otel_log_group_name" { value = aws_cloudwatch_log_group.otel.name }
output "otel_log_group_arn" { value = aws_cloudwatch_log_group.otel.arn }
output "chaos_parameters" { value = { for key, parameter in aws_ssm_parameter.chaos : local.apps[key].discovery => parameter.name } }
output "chaos_parameter_arns" { value = [for parameter in aws_ssm_parameter.chaos : parameter.arn] }
output "grafana_secret_arn" { value = aws_secretsmanager_secret.grafana.arn }
