variable "cluster_name" {
  default = "a-cluster-name"
}

variable "kubernetes_version" {
  default = "1.8.8"
}

variable "region" {
  default = "us-central1"
}

variable "region_zone" {
  default = "us-central1-f"
}

variable "host_project" {
  description = "The ID of the Google Cloud project"
}

variable "service_project" {
  description = "The ID of the Google Cloud project"
}

variable "master_ip_range" {
  default = "172.16.0.0/28"
}

variable "network" {
  default = "gke-network"
}

variable "subnetwork" {
  default = "gke-subnet"
}

variable "subnetwork_ip_range" {
  default = "10.0.0.0/14"
}

variable "secondary_cluster_range_name" {
  default = "pods-block"
}

variable "secondary_services_range_name" {
  default = "services-block"
}

variable "secondary_cluster_ip_range" {
  default = "10.96.0.0/16"
}

variable "secondary_services_ip_range" {
  default = "10.94.0.0/20"
}
