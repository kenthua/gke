resource "google_project_iam_member" "host_service_agent" {
  project = "${var.host_project}"
  role    = "roles/container.hostServiceAgentUser"
  member  = "serviceAccount:service-${data.google_project.service_project.number}@container-engine-robot.iam.gserviceaccount.com"
}

/*
* Seems to be a workaround for the google_compute_subnetwork_iam_binding 
*/
resource "google_project_iam_binding" "compute-networkuser" {
  project = "${var.host_project}"
  role    = "roles/compute.networkUser"

  members = [
    "serviceAccount:${data.google_project.service_project.number}@cloudservices.gserviceaccount.com",
    "serviceAccount:service-${data.google_project.service_project.number}@container-engine-robot.iam.gserviceaccount.com",
  ]
}
