output "cluster_name" {
  value = "${google_container_cluster.cluster0.name}"
}

output "primary_location" {
  value = "${google_container_cluster.cluster0.location}"
}

output "additional_zones" {
  value = "${google_container_cluster.cluster0.additional_zones}"
}

output "endpoint" {
  value = "${google_container_cluster.cluster0.endpoint}"
}

output "node_version" {
  value = "${google_container_cluster.cluster0.node_version}"
}
