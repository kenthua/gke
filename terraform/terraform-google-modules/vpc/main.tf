locals {
  host_project_id         = "kenthua-altostrat-host"
  service_project_id      = "kenthua-altostrat-service"
  network_name            = "gke-network"
  subnet_name             = "gke-subnet"
  pod_cidr_range_name     = "pod-cidr"
  service_cidr_range_name = "service-cidr"
  region                  = "us-west1"
}

module "vpc" {
  source = "github.com/terraform-google-modules/terraform-google-network"

  project_id   = "${local.host_project_id}"
  network_name = "${local.network_name}"

  # 10.100.10.0 - 10.100.10.255 (256)
  subnets = [
    {
      subnet_name           = "${local.subnet_name}"
      subnet_ip             = "10.100.10.0/24"
      subnet_region         = "${local.region}"
      subnet_private_access = "true"
      subnet_flow_logs      = "true"
    },
  ]

  # 10.100.16.0 - 10.100.23.255 (2048)
  # 10.200.24.0 - 10.200.24.255 (256)
  secondary_ranges = {
    "${local.subnet_name}" = [
      {
        range_name    = "${local.pod_cidr_range_name}"
        ip_cidr_range = "10.100.16.0/21"
      },
      {
        range_name    = "${local.service_cidr_range_name}"
        ip_cidr_range = "10.100.24.0/24"
      },
    ]
  }
}
