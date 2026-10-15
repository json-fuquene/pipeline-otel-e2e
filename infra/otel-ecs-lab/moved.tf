moved {
  from = aws_ecr_repository.images
  to   = module.ecr.aws_ecr_repository.images
}

moved {
  from = random_password.database
  to   = module.foundation.random_password.database
}

moved {
  from = aws_secretsmanager_secret.database
  to   = module.foundation.aws_secretsmanager_secret.database
}

moved {
  from = aws_secretsmanager_secret_version.database
  to   = module.foundation.aws_secretsmanager_secret_version.database
}

moved {
  from = aws_cloudwatch_log_group.ecs
  to   = module.foundation.aws_cloudwatch_log_group.ecs
}

moved {
  from = aws_cloudwatch_log_group.otel
  to   = module.foundation.aws_cloudwatch_log_group.otel
}

moved {
  from = aws_vpc.lab
  to   = module.network.aws_vpc.lab
}

moved {
  from = aws_internet_gateway.lab
  to   = module.network.aws_internet_gateway.lab
}

moved {
  from = aws_subnet.public
  to   = module.network.aws_subnet.public
}

moved {
  from = aws_route_table.public
  to   = module.network.aws_route_table.public
}

moved {
  from = aws_route_table_association.public
  to   = module.network.aws_route_table_association.public
}

moved {
  from = aws_security_group.task
  to   = module.network.aws_security_group.task
}

moved {
  from = aws_ecs_cluster.lab
  to   = module.ecs.aws_ecs_cluster.lab
}

moved {
  from = aws_iam_role.execution
  to   = module.foundation.aws_iam_role.execution
}

moved {
  from = aws_iam_role_policy_attachment.execution_managed
  to   = module.foundation.aws_iam_role_policy_attachment.execution_managed
}

moved {
  from = aws_iam_role_policy.execution_secret
  to   = module.foundation.aws_iam_role_policy.execution_secret
}

moved {
  from = aws_iam_role.task
  to   = module.foundation.aws_iam_role.task
}

moved {
  from = aws_iam_role_policy.task_logs
  to   = module.foundation.aws_iam_role_policy.task_logs
}

moved {
  from = aws_ecs_task_definition.lab
  to   = module.ecs.aws_ecs_task_definition.lab
}

moved {
  from = aws_ecs_service.lab
  to   = module.ecs.aws_ecs_service.lab
}
