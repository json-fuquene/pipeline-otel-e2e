output "ecr_urls" {
  description = "Repositorios ECR; guardarlos en un JSON para scripts/push-ecs-images.py."
  value       = module.ecr.ecr_urls
}
output "cluster_name" { value = module.ecs.cluster_name }
output "service_names" { value = module.ecs.service_names }
output "service_connect_namespace" { value = module.ecs.namespace_name }
output "rds_endpoint" { value = "${module.rds.address}:${module.rds.port}" }
output "chaos_parameters" { value = module.ecs.chaos_parameters }
output "alarm_names" { value = merge(module.aiops.alarm_names, { security = module.security.alarm_names }) }
output "enriched_topic_arn" { value = module.aiops.enriched_topic_arn }
output "log_groups" {
  value = {
    otel      = module.ecs.otel_log_group_name
    ecs       = module.ecs.ecs_log_group_name
    flow_logs = module.network.flow_log_group_name
    findings  = module.security.findings_log_group_name
    alerts    = module.aiops.enricher_log_group_name
  }
}
output "lab_config" {
  description = "Configuración consumida por los scripts de caos, carga y ruido (guardar con terraform output -json lab_config)."
  value = {
    region           = var.aws_region
    cluster          = module.ecs.cluster_name
    services         = module.ecs.service_names
    chaos_parameters = module.ecs.chaos_parameters
    alarms           = module.aiops.alarm_names
    latency_slo_ms   = var.latency_slo_ms
    otel_log_group   = module.ecs.otel_log_group_name
    alerts_log_group = module.aiops.enricher_log_group_name
  }
}
