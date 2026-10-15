locals {
  name        = "pipeline-otel-test"
  image_names = ["catalog", "orders", "postgres", "otel-collector", "jaeger", "prometheus"]
}

module "ecr" {
  source      = "../tf_modules/ecr"
  name        = local.name
  image_names = local.image_names
}

module "network" {
  source       = "../tf_modules/network"
  name         = local.name
  allowed_cidr = var.allowed_cidr
}

module "foundation" {
  source              = "../tf_modules/foundation"
  name                = local.name
  log_group_name      = "/ecs/${local.name}"
  otel_log_group_name = "/pipeline-otel/ecs-test"
}

module "ecs" {
  source              = "../tf_modules/ecs"
  name                = local.name
  aws_region          = var.aws_region
  desired_count       = var.desired_count
  image_tag           = var.image_tag
  ecr_urls            = module.ecr.ecr_urls
  database_secret_arn = module.foundation.database_secret_arn
  execution_role_arn  = module.foundation.execution_role_arn
  task_role_arn       = module.foundation.task_role_arn
  log_group_name      = module.foundation.log_group_name
  subnet_ids          = module.network.subnet_ids
  security_group_id   = module.network.security_group_id
  depends_on          = [module.network, module.foundation]
}
