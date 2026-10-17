resource "aws_db_subnet_group" "lab" {
  name       = var.name
  subnet_ids = var.subnet_ids
  tags       = { Name = var.name }
}

resource "aws_db_parameter_group" "lab" {
  name   = var.name
  family = "postgres${split(".", var.engine_version)[0]}"

  # TLS obligatorio y registro de sentencias lentas para correlacionar con los spans DB.
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
  parameter {
    name  = "log_min_duration_statement"
    value = "250"
  }
}

resource "aws_db_instance" "lab" {
  identifier     = var.name
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  db_name                     = var.database_name
  username                    = var.master_username
  manage_master_user_password = true

  allocated_storage      = 20
  storage_type           = "gp3"
  storage_encrypted      = true
  db_subnet_group_name   = aws_db_subnet_group.lab.name
  vpc_security_group_ids = [var.security_group_id]
  parameter_group_name   = aws_db_parameter_group.lab.name
  publicly_accessible    = false
  multi_az               = false

  # Laboratorio efímero: sin respaldos ni snapshot final (RNF de costo, ver ID-003).
  backup_retention_period  = 0
  skip_final_snapshot      = true
  deletion_protection      = false
  delete_automated_backups = true
  apply_immediately        = true

  # DevOps Guru for RDS requiere Performance Insights; logs de PostgreSQL a CloudWatch.
  performance_insights_enabled          = var.performance_insights_enabled
  performance_insights_retention_period = var.performance_insights_enabled ? 7 : null
  enabled_cloudwatch_logs_exports       = ["postgresql"]
  monitoring_interval                   = 0

  tags = merge(var.tags, { Name = var.name })
}
