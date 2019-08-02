resource "google_container_cluster" "cluster0" {
  provider = "google-beta"
  name                     = "${var.cluster_name}"
  location                   = "${var.location}"
  network                  = "${google_compute_network.gke-network.self_link}"
  subnetwork              = "${google_compute_subnetwork.gke-subnet.self_link}"
  remove_default_node_pool = true

  #zone               = "${data.google_compute_zones.available.names[0]}" # for zonal
  #initial_node_count = 1

  min_master_version = "${var.kubernetes_version}"
  node_version       = "${var.kubernetes_version}"
  ip_allocation_policy {
    use_ip_aliases = true
    services_secondary_range_name = "service-cidr"
    cluster_secondary_range_name = "pod-cidr"
  }

  node_pool {
    name = "default-pool"
  }
  authenticator_groups_config {
    security_group = "${var.security_group}"

  }
  lifecycle {
    ignore_changes = ["node_pool", "node_version", "network"]
  }

  depends_on = [google_compute_subnetwork.gke-subnet]
}

resource "google_container_node_pool" "nodepool0" {
  provider = "google-beta"
  cluster = "${google_container_cluster.cluster0.name}"
  location  = "${var.location}"
  name    = "dev-pool"

  node_count = 3

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    preemptible = true

    oauth_scopes = [
      "https://www.googleapis.com/auth/compute",
      "https://www.googleapis.com/auth/devstorage.read_only",
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring",
    ]

    tags = ["dev", "pool"]
  }
}

resource "google_compute_subnetwork" "gke-subnet" {
  name          = "gke-sub"
  ip_cidr_range = "10.100.0.0/24"
  region        = "us-central1"
  network       = "${google_compute_network.gke-network.self_link}"
  secondary_ip_range {
    range_name    = "pod-cidr"
    ip_cidr_range = "192.168.0.0/19"
  }
  secondary_ip_range {
    range_name    = "service-cidr"
    ip_cidr_range = "172.16.10.0/24"
  }
  
  depends_on = [google_compute_network.gke-network]
}

resource "google_compute_network" "gke-network" {
  provider = "google-beta"
  name                    = "gke-network"
  auto_create_subnetworks = false
}