data "terraform_remote_state" "persistent" {
  backend = "local"

  config = {
    path = "../persistent/terraform.tfstate"
  }
}