provider "google" {
  #credentials = "${file("service_account.json")}"
  region  = "${var.region}"
  project = "${var.project}"

  # See here more details
  # https://www.terraform.io/docs/providers/google/index.html
}
