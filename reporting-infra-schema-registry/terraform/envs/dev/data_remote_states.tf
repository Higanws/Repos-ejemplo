data "terraform_remote_state" "phase2" {
  backend = "s3"
  config = {
    bucket = var.phase2_state_bucket
    key    = var.phase2_state_key
    region = var.phase2_state_region
  }
}

data "terraform_remote_state" "phase3" {
  backend = "s3"
  config = {
    bucket = var.phase3_state_bucket
    key    = var.phase3_state_key
    region = var.phase3_state_region
  }
}
