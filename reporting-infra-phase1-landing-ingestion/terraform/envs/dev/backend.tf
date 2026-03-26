# Bucket de state (sa-east-1). Cada fase usa un key distinto. Versionado en S3 recomendado en prod.
terraform {
  backend "s3" {
    bucket = "angel-reporting-tfstate"
    key    = "reporting-phase1-landing-ingestion/dev/terraform.tfstate"
    region = "sa-east-1"
  }
}
