data "google_compute_zones" "available" {}

resource "google_container_cluster" "cluster0" {
  name                     = "${var.cluster_name}"
  region                   = "${var.region}"
  network                  = "default"
  remove_default_node_pool = true

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
}

resource "google_container_node_pool" "nodepool0" {
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
}
