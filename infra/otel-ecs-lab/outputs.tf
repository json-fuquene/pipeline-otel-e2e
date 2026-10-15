output "ecr_urls" {
  description = "URL de los repositorios donde publicar las imágenes del laboratorio."
  value       = module.ecr.ecr_urls
}
output "cluster_name" { value = module.ecs.cluster_name }
output "service_name" { value = module.ecs.service_name }
output "security_group_id" { value = module.network.security_group_id }
output "endpoints" {
  value = "La IP pública de la tarea aparece en ECS > ${module.ecs.cluster_name} > Tasks. Puertos: 8001 catálogo, 8002 pedidos, 16686 Jaeger, 9090 Prometheus."
}
