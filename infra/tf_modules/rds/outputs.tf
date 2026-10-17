output "address" { value = aws_db_instance.lab.address }
output "port" { value = aws_db_instance.lab.port }
output "identifier" { value = aws_db_instance.lab.identifier }
output "arn" { value = aws_db_instance.lab.arn }
output "database_name" { value = aws_db_instance.lab.db_name }
output "master_secret_arn" {
  description = "Secreto administrado por RDS con las claves username y password."
  value       = aws_db_instance.lab.master_user_secret[0].secret_arn
}
