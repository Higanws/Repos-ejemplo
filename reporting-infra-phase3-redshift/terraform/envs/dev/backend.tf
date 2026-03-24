terraform {
  backend "s3" {
    bucket = "ngel-reporting-tfstate-sa1-131189842834-sa-east-1-an"
    key    = "reporting-phase3-redshift/dev/terraform.tfstate"
    region = "sa-east-1"
  }
}
