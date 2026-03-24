data "terraform_remote_state" "phase1" {
  backend = "s3"

  config = {
    bucket = var.phase1_state_bucket
    key    = var.phase1_state_key
    region = var.phase1_state_region
  }
}

data "aws_s3_bucket" "raw" {
  bucket = data.terraform_remote_state.phase1.outputs.s3_raw_bucket
}
