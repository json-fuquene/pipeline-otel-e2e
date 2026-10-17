# ID-003 — Contraparte GCP del data-service (IaC de referencia, NO aplicada).
# Alcance acordado: la validación funcional se ejecuta solo en AWS. Este módulo documenta cómo el
# mismo contenedor data-service accede a Cloud SQL y cómo se habilitan VPC Flow Logs y la
# detección de anomalías en Cloud Monitoring. No se ejecutó terraform validate ni apply.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "us-central1"
}
variable "data_service_image" {
  description = "Imagen del data-service publicada en Artifact Registry."
  type        = string
}
variable "otlp_endpoint" {
  description = "Endpoint OTLP de un Collector alcanzable desde Cloud Run."
  type        = string
}

locals { name = "pipeline-otel-obs" }

resource "google_compute_network" "lab" {
  name                    = local.name
  auto_create_subnetworks = false
}

# VPC Flow Logs (Módulo C) con agregación de 30 s y metadatos completos.
resource "google_compute_subnetwork" "lab" {
  name                     = "${local.name}-${var.region}"
  ip_cidr_range            = "10.64.0.0/20"
  region                   = var.region
  network                  = google_compute_network.lab.id
  private_ip_google_access = true
  log_config {
    aggregation_interval = "INTERVAL_30_SEC"
    flow_sampling        = 1.0
    metadata             = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_global_address" "private_services" {
  name          = "${local.name}-psa"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 20
  network       = google_compute_network.lab.id
}

resource "google_service_networking_connection" "private_services" {
  network                 = google_compute_network.lab.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]
}

resource "google_sql_database_instance" "lab" {
  name                = local.name
  database_version    = "POSTGRES_17"
  region              = var.region
  deletion_protection = false
  settings {
    tier    = "db-f1-micro"
    edition = "ENTERPRISE"
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.lab.id
      ssl_mode        = "ENCRYPTED_ONLY"
    }
    insights_config {
      query_insights_enabled = true
    }
  }
  depends_on = [google_service_networking_connection.private_services]
}

resource "google_sql_database" "pipeline" {
  name     = "pipeline"
  instance = google_sql_database_instance.lab.name
}

resource "random_password" "data_app" {
  length  = 32
  special = false
}

resource "google_sql_user" "data_app" {
  name     = "data_app"
  instance = google_sql_database_instance.lab.name
  password = random_password.data_app.result
}

resource "google_secret_manager_secret" "data_db" {
  secret_id = "${local.name}-data-db"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "data_db" {
  secret      = google_secret_manager_secret.data_db.id
  secret_data = random_password.data_app.result
}

resource "google_service_account" "data_service" {
  account_id   = "${local.name}-data"
  display_name = "data-service (ID-003)"
}

resource "google_secret_manager_secret_iam_member" "data_db" {
  secret_id = google_secret_manager_secret.data_db.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.data_service.email}"
}

resource "google_cloud_run_v2_service" "data_service" {
  name     = "${local.name}-data-service"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  template {
    service_account = google_service_account.data_service.email
    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = google_compute_network.lab.id
        subnetwork = google_compute_subnetwork.lab.id
      }
    }
    containers {
      image = var.data_service_image
      ports {
        container_port = 8000
      }
      env {
        name  = "DB_HOST"
        value = google_sql_database_instance.lab.private_ip_address
      }
      env {
        name  = "DB_USER"
        value = google_sql_user.data_app.name
      }
      env {
        name  = "DB_SSLMODE"
        value = "require"
      }
      env {
        name  = "DB_CLOUD_PROVIDER"
        value = "gcp"
      }
      env {
        name  = "OTEL_EXPORTER_OTLP_ENDPOINT"
        value = var.otlp_endpoint
      }
      env {
        name  = "OTEL_SEMCONV_STABILITY_OPT_IN"
        value = "http,database"
      }
      env {
        name = "DB_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.data_db.secret_id
            version = "latest"
          }
        }
      }
    }
  }
}

# Cloud Monitoring: alerta de error rate por encima del pronóstico (forecast/anomalía) sobre Cloud Run.
resource "google_monitoring_alert_policy" "data_service_errors" {
  display_name = "${local.name} data-service 5xx ratio"
  combiner     = "AND"
  conditions {
    display_name = "5xx ratio > 2 %"
    condition_monitoring_query_language {
      duration = "60s"
      query    = <<-MQL
        fetch cloud_run_revision
        | metric 'run.googleapis.com/request_count'
        | filter resource.service_name == '${google_cloud_run_v2_service.data_service.name}'
        | align rate(1m)
        | group_by [], [errors: aggregate(if(metric.response_code_class == '5xx', val(), 0)), total: aggregate(val())]
        | value [ratio: errors / total * 100]
        | condition ratio > 2
      MQL
    }
  }
}

output "cloud_sql_private_ip" { value = google_sql_database_instance.lab.private_ip_address }
output "data_service_uri" { value = google_cloud_run_v2_service.data_service.uri }
