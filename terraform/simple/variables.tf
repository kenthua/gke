variable "cluster_name" {
  default = "a-cluster-name"
}

variable "kubernetes_version" {
  default = "1.8.8"
}

variable "location" {
  default = "us-central1"
}

variable "region_zone" {
  default = "us-central1-f"
}

variable "project" {
  description = "The ID of the Google Cloud project"
}

variable "security_group" {
  default = "gke-security-groups@yourdomain.com"
}