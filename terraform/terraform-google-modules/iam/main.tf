locals {
  host_project_id         = "kenthua-altostrat-host"
  service_project_id      = "kenthua-altostrat-service"
  network_name            = "gke-network"
  subnet_name             = "gke-subnet"
  pod_cidr_range_name     = "pod-cidr"
  service_cidr_range_name = "service-cidr"
  region                  = "us-west1"
  subnet_full = "${format ("projects/%s/regions/%s/subnetworks/%s", local.host_project_id, local.region, local.subnet_name)}"

}

data "google_project" "host_project" {
  project_id = "${local.host_project_id}"
}

data "google_project" "service_project" {
  project_id = "${local.service_project_id}"
}

module "iam_binding" {
  source = "github.com/terraform-google-modules/terraform-google-iam?ref=v1.0.0"

  projects = ["${local.host_project_id}"]

  bindings = {
    "roles/container.hostServiceAgentUser" = [
      "serviceAccount:service-${data.google_project.service_project.number}@container-engine-robot.iam.gserviceaccount.com"
    ]
  }
}

module "subnet_iam_binding" {
  source = "github.com/terraform-google-modules/terraform-google-iam?ref=v1.0.0"

  subnets = ["${local.subnet_full}"]

  bindings = {
    "roles/compute.networkUser" = [
      "serviceAccount:service-${data.google_project.service_project.number}@container-engine-robot.iam.gserviceaccount.com",
      "serviceAccount:${data.google_project.service_project.number}@cloudservices.gserviceaccount.com"
    ]
  }
}