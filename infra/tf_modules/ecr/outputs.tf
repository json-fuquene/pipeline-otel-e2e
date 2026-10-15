output "ecr_urls" {
  description = "URL de los repositorios ECR por imagen."
  value       = { for name, repository in aws_ecr_repository.images : name => repository.repository_url }
}
