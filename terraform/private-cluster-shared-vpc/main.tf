data "google_project" "host_project" {
  project_id = "${var.host_project}"
}

data "google_project" "service_project" {
  project_id = "${var.service_project}"
}

data "google_compute_zones" "available" {
  project = "${var.service_project}"
}

resource "google_container_cluster" "cluster0" {
  project                  = "${var.service_project}"
  name                     = "${var.cluster_name}"
  region                   = "${var.region}"
  network                  = "${google_compute_network.network0.self_link}"
  subnetwork               = "${google_compute_subnetwork.subnet0.self_link}"
  remove_default_node_pool = true

  addons_config {
    kubernetes_dashboard {
      disabled = true
    }

    http_load_balancing {
      disabled = false #enabled by default
    }
  }

  private_cluster        = true
  master_ipv4_cidr_block = "${var.master_ip_range}"

  ip_allocation_policy {
    cluster_secondary_range_name  = "${google_compute_subnetwork.subnet0.secondary_ip_range.0.range_name}"
    services_secondary_range_name = "${google_compute_subnetwork.subnet0.secondary_ip_range.1.range_name}"
  }

  #zone               = "${data.google_compute_zones.available.names[0]}" # for zonal
  #initial_node_count = 1

  min_master_version = "${var.kubernetes_version}"
  node_version       = "${var.kubernetes_version}"
  additional_zones = [
    "${data.google_compute_zones.available.names[1]}",
    "${data.google_compute_zones.available.names[2]}",
  ]
  node_pool {
    name = "default-pool"
  }
  lifecycle {
    ignore_changes = ["node_pool", "node_version", "network"]
  }
  depends_on = ["google_project_iam_member.host_service_agent", "google_project_iam_binding.compute-networkuser", "google_compute_subnetwork.subnet0"]
}

resource "google_container_node_pool" "nodepool0" {
  project = "${var.service_project}"
  cluster = "${google_container_cluster.cluster0.name}"
  region  = "${var.region}"
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

    labels {
      env      = "dev"
      pipeline = "cicd"
    }

    tags = ["dev", "pool"]
  }

  depends_on = ["google_container_cluster.cluster0"]
}
