output "database_secret_arn" { value = aws_secretsmanager_secret.database.arn }
output "execution_role_arn" { value = aws_iam_role.execution.arn }
output "task_role_arn" { value = aws_iam_role.task.arn }
output "log_group_name" { value = aws_cloudwatch_log_group.ecs.name }
