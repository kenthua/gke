provider "google-beta" {
  #credentials = "${file("service_account.json")}"
  region  = "${var.location}"
  project = "${var.project}"

  # See here more details
  # https://www.terraform.io/docs/providers/google/index.html
}
provider "google" {
  #credentials = "${file("service_account.json")}"
  region  = "${var.location}"
  project = "${var.project}"

  # See here more details
  # https://www.terraform.io/docs/providers/google/index.html
}
