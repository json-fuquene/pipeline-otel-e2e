locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 2)
  # Formato de VPC Flow Logs: campos v2 por defecto + pkt-src/dst y dirección (v5).
  # Las consultas Logs Insights y los filtros de métricas dependen de este orden exacto.
  flow_log_format = join(" ", [
    "$${version}", "$${account-id}", "$${interface-id}", "$${srcaddr}", "$${dstaddr}",
    "$${srcport}", "$${dstport}", "$${protocol}", "$${packets}", "$${bytes}", "$${start}",
    "$${end}", "$${action}", "$${log-status}", "$${pkt-srcaddr}", "$${pkt-dstaddr}", "$${flow-direction}"
  ])
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "lab" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = { Name = var.name }
}

resource "aws_internet_gateway" "lab" {
  vpc_id = aws_vpc.lab.id
  tags   = { Name = var.name }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.lab.id
  cidr_block              = cidrsubnet(aws_vpc.lab.cidr_block, 8, count.index + 1)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.name}-public-${count.index + 1}", Tier = "public" }
}

# Subredes privadas sin ruta a Internet: solo alojan Amazon RDS.
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.lab.id
  cidr_block        = cidrsubnet(aws_vpc.lab.cidr_block, 8, count.index + 11)
  availability_zone = local.azs[count.index]
  tags              = { Name = "${var.name}-private-${count.index + 1}", Tier = "private" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.lab.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.lab.id
  }
  tags = { Name = "${var.name}-public" }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "tasks" {
  name        = "${var.name}-tasks"
  description = "ECS tasks of the observable lab."
  vpc_id      = aws_vpc.lab.id
  tags        = { Name = "${var.name}-tasks" }
}

# Norte-sur: solo el CIDR autorizado llega a las APIs públicas y consolas.
resource "aws_vpc_security_group_ingress_rule" "public_ports" {
  for_each          = toset([for port in var.public_ports : tostring(port)])
  security_group_id = aws_security_group.tasks.id
  cidr_ipv4         = var.allowed_cidr
  from_port         = tonumber(each.value)
  to_port           = tonumber(each.value)
  ip_protocol       = "tcp"
  description       = "North-south access from the authorized CIDR"
}

# Este-oeste: tráfico entre tareas (Service Connect, OTLP, scrape de métricas).
resource "aws_vpc_security_group_ingress_rule" "east_west" {
  security_group_id            = aws_security_group.tasks.id
  referenced_security_group_id = aws_security_group.tasks.id
  ip_protocol                  = "tcp"
  from_port                    = 1
  to_port                      = 65535
  description                  = "East-west traffic between lab tasks"
}

resource "aws_vpc_security_group_egress_rule" "tasks_all" {
  security_group_id = aws_security_group.tasks.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "Image pulls, AWS APIs and RDS"
}

resource "aws_security_group" "database" {
  name        = "${var.name}-database"
  description = "PostgreSQL reachable only from lab tasks."
  vpc_id      = aws_vpc.lab.id
  tags        = { Name = "${var.name}-database" }
}

resource "aws_vpc_security_group_ingress_rule" "database_from_tasks" {
  security_group_id            = aws_security_group.database.id
  referenced_security_group_id = aws_security_group.tasks.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  description                  = "PostgreSQL from ECS tasks"
}

# ---------------------------------------------------------------------------
# VPC Flow Logs → CloudWatch Logs (Módulo C)
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "flow_logs" {
  name              = var.flow_log_group_name
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "flow_logs" {
  name = "${var.name}-flow-logs"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "vpc-flow-logs.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id } }
    }]
  })
}

data "aws_caller_identity" "current" {}

resource "aws_iam_role_policy" "flow_logs" {
  name = "write-flow-logs"
  role = aws_iam_role.flow_logs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogGroups", "logs:DescribeLogStreams"]
      Resource = ["${aws_cloudwatch_log_group.flow_logs.arn}", "${aws_cloudwatch_log_group.flow_logs.arn}:*"]
    }]
  })
}

resource "aws_flow_log" "vpc" {
  vpc_id                   = aws_vpc.lab.id
  traffic_type             = "ALL"
  log_destination_type     = "cloud-watch-logs"
  log_destination          = aws_cloudwatch_log_group.flow_logs.arn
  iam_role_arn             = aws_iam_role.flow_logs.arn
  log_format               = local.flow_log_format
  max_aggregation_interval = 60
  tags                     = { Name = "${var.name}-vpc-flow-logs" }
}
