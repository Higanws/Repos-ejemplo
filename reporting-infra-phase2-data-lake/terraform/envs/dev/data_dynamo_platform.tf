data "terraform_remote_state" "dynamo_platform" {
  count   = var.enable_pipeline_dynamo ? 1 : 0
  backend = "s3"
  config = {
    bucket = var.dynamo_platform_state_bucket
    key    = var.dynamo_platform_state_key
    region = var.aws_region
  }
}
