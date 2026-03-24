# Copiá a backend.hcl o configurá -backend en CI. Key único por repo.
terraform {
  backend "s3" {
    bucket = "angel-reporting-tfstate"
    key    = "reporting-dynamo-platform/dev/terraform.tfstate"
    region = "sa-east-1"
  }
}
