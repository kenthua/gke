resource "google_compute_network" "network0" {
  name                    = "${var.network}"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet0" {
  name          = "${google_compute_network.network0.self_link}"
  region        = "${var.region}"
  network       = "${var.network}"
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