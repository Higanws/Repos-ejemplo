data "terraform_remote_state" "phase1" {
  backend = "s3"
  config = {
    bucket = var.phase1_state_bucket
    key    = var.phase1_state_key
    region = var.phase1_state_region
  }
}

data "terraform_remote_state" "phase2" {
  backend = "s3"
  config = {
    bucket = var.phase2_state_bucket
    key    = var.phase2_state_key
    region = var.phase2_state_region
  }
}

data "aws_s3_bucket" "raw" {
  bucket = data.terraform_remote_state.phase1.outputs.s3_raw_bucket
}

data "aws_s3_bucket" "standardized" {
  bucket = data.terraform_remote_state.phase2.outputs.s3_standardized_bucket
}

data "aws_s3_bucket" "silver" {
  bucket = data.terraform_remote_state.phase2.outputs.s3_silver_bucket
}

data "aws_s3_bucket" "artifacts" {
  bucket = data.terraform_remote_state.phase2.outputs.s3_artifacts_bucket
}
