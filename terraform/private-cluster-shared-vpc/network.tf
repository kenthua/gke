resource "google_compute_network" "network0" {
  project                 = "${var.host_project}"
  name                    = "${var.network}"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet0" {
  project       = "${var.host_project}"
  name          = "${var.subnetwork}"
  region        = "${var.region}"
  network       = "${google_compute_network.network0.self_link}"
  ip_cidr_range = "${var.subnetwork_ip_range}"

  secondary_ip_range = {
    range_name    = "${var.secondary_cluster_range_name}"
    ip_cidr_range = "${var.secondary_cluster_ip_range}"
  }

  secondary_ip_range = {
    range_name    = "${var.secondary_services_range_name}"
    ip_cidr_range = "${var.secondary_services_ip_range}"
  }

  depends_on = ["google_compute_network.network0"]
}

/*
* Cannot do this yet because, can't specify etag
*/
/*resource "google_compute_subnetwork_iam_binding" "subnet" {
  project = "${var.host_project}"
  subnetwork = "${var.subnetwork}"
  role       = "roles/compute.networkUser"

  members = [
    "serviceAccount:${data.google_project.service_project.number}@cloudservices.gserviceaccount.com",
    "serviceAccount:service-${data.google_project.service_project.number}@container-engine-robot.iam.gserviceaccount.com"
  ]

  depends_on = ["google_compute_subnetwork.subnet0"]
}
*/

