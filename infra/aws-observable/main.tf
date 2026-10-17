locals {
  name     = "pipeline-otel-obs"
  vpc_cidr = "10.63.0.0/16"
  images   = ["catalog", "orders", "data", "postgres", "otel-collector", "jaeger", "prometheus", "grafana"]

  # Frontera de análisis de DevOps Guru: la clave debe empezar por "DevOps-Guru-".
  devops_guru_tag_key   = "DevOps-Guru-${local.name}"
  devops_guru_tag_value = "data-service"
  devops_guru_tags      = { (local.devops_guru_tag_key) = local.devops_guru_tag_value }
  tags                  = { Lab = local.name }
}

module "ecr" {
  source      = "../tf_modules/ecr"
  name        = local.name
  image_names = local.images
}

module "network" {
  source              = "../tf_modules/vpc-observable"
  name                = local.name
  vpc_cidr            = local.vpc_cidr
  allowed_cidr        = var.allowed_cidr
  public_ports        = [8001, 8002, 3000, 16686, 9090]
  flow_log_group_name = "/vpc/${local.name}/flow-logs"
  log_retention_days  = var.log_retention_days
}

module "rds" {
  source                       = "../tf_modules/rds"
  name                         = local.name
  subnet_ids                   = module.network.private_subnet_ids
  security_group_id            = module.network.database_security_group_id
  engine_version               = var.db_engine_version
  instance_class               = var.db_instance_class
  database_name                = "pipeline"
  master_username              = "pipeline_admin"
  performance_insights_enabled = var.db_performance_insights
  tags                         = merge(local.tags, local.devops_guru_tags)
}

module "ecs" {
  source               = "../tf_modules/ecs-observable"
  name                 = local.name
  aws_region           = var.aws_region
  environment          = "aws-sandbox"
  desired_count        = var.desired_count
  image_tag            = var.image_tag
  ecr_urls             = module.ecr.ecr_urls
  subnet_ids           = module.network.public_subnet_ids
  security_group_id    = module.network.tasks_security_group_id
  db_address           = module.rds.address
  db_port              = module.rds.port
  db_name              = module.rds.database_name
  db_master_secret_arn = module.rds.master_secret_arn
  otel_log_group_name  = "/pipeline-otel/${local.name}"
  log_retention_days   = var.log_retention_days
  container_insights   = var.container_insights
  extra_readable_log_group_arns = [
    module.network.flow_log_group_arn,
    module.security.findings_log_group_arn,
    module.aiops.enricher_log_group_arn,
  ]
  tags             = local.tags
  devops_guru_tags = local.devops_guru_tags
}

module "aiops" {
  source                  = "../tf_modules/aiops"
  name                    = local.name
  aws_region              = var.aws_region
  otel_log_group_name     = module.ecs.otel_log_group_name
  otel_log_group_arn      = module.ecs.otel_log_group_arn
  flow_log_group_name     = module.network.flow_log_group_name
  findings_log_group_name = module.security.findings_log_group_name
  ecs_log_group_name      = module.ecs.ecs_log_group_name
  vpc_cidr                = local.vpc_cidr
  extra_query_log_group_arns = [
    module.network.flow_log_group_arn,
    module.security.findings_log_group_arn,
    module.ecs.ecs_log_group_arn,
  ]
  latency_slo_ms        = var.latency_slo_ms
  static_error_rate_pct = var.static_error_rate_pct
  anomaly_band_stddev   = var.anomaly_band_stddev
  alert_email           = var.alert_email
  lambda_source_dir     = "${path.root}/../lambda"
  log_retention_days    = var.log_retention_days
  enable_devops_guru    = var.enable_devops_guru
  devops_guru_tag_key   = local.devops_guru_tag_key
  devops_guru_tag_value = local.devops_guru_tag_value
  tags                  = local.tags
}

module "security" {
  source                   = "../tf_modules/security-observability"
  name                     = local.name
  aws_region               = var.aws_region
  vpc_cidr                 = local.vpc_cidr
  flow_log_group_name      = module.network.flow_log_group_name
  ecs_log_group_name       = module.ecs.ecs_log_group_name
  alarm_topic_arn          = module.aiops.raw_topic_arn
  lambda_source_dir        = "${path.root}/../lambda"
  log_retention_days       = var.log_retention_days
  enable_security_hub      = var.enable_security_hub
  enable_inspector         = var.enable_inspector
  enable_guardduty         = var.enable_guardduty
  rejected_flows_threshold = 50
  failed_auth_threshold    = 5
  tags                     = local.tags
}
