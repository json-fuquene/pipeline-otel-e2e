output "subnet_ids" { value = aws_subnet.public[*].id }
output "security_group_id" { value = aws_security_group.task.id }
