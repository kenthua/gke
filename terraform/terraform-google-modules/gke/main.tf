locals {
  host_project_id         = "kenthua-altostrat-host"
  service_project_id      = "kenthua-altostrat-service"
  network_name            = "gke-network"
  subnet_name             = "gke-subnet"
  pod_cidr_range_name     = "pod-cidr"
  service_cidr_range_name = "service-cidr"
  region                  = "us-west1"
}

module "gke" {
  source                     = "github.com/terraform-google-modules/terraform-google-kubernetes-engine?ref=v0.3.0"
  project_id                 = "${local.service_project_id}"
  name                       = "tf-cluster"
  region                     = "${local.region}"
  regional                   = true
  zones                      = ["us-west1-a", "us-west1-b", "us-west1-c"]
  network                    = "${local.network_name}"
  network_project_id         = "${local.host_project_id}"
  subnetwork                 = "${local.subnet_name}"
  ip_range_pods              = "${local.pod_cidr_range_name}"
  ip_range_services          = "${local.service_cidr_range_name}"
  http_load_balancing        = false
  horizontal_pod_autoscaling = true
  kubernetes_dashboard       = false
  network_policy             = true

  kubernetes_version         = "1.10"

  # private                                        = true
  # private_cluster_config_enable_private_endpoint = false
  # private_cluster_config_enable_private_nodes    = true
  # private_cluster_config_master_ipv4_cidr_block  = "172.16.0.0/28"
  # master_authorized_networks_config = [{
  #   cidr_blocks = [{
  #     cidr_block = "0.0.0.0/0"
  #     display_name = "open"
  #   }]
  # }]


  node_pools = [
    {
      name            = "default-node-pool"
      machine_type    = "n1-standard-2"
      min_count       = 1
      max_count       = 100
      disk_size_gb    = 30
      disk_type       = "pd-standard"
      image_type      = "COS"
      auto_repair     = true
      auto_upgrade    = true
      preemptible     = true
    },
  ]

  node_pools_labels = {
    all = {}

    default-node-pool = {
      default-node-pool = "true"
    }
  }

  node_pools_taints = {
    all = []

    default-node-pool = [
      {
        key    = "default-node-pool"
        value  = "true"
        effect = "PREFER_NO_SCHEDULE"
      },
    ]
  }

  node_pools_tags = {
    all = []

    default-node-pool = [
      "default-node-pool",
    ]
  }
}
