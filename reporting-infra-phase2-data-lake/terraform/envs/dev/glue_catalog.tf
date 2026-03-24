resource "aws_glue_catalog_database" "raw" {
  name = "raw"
}

resource "aws_glue_catalog_database" "standardized_s3" {
  name = "standardized_s3"
}

resource "aws_glue_catalog_database" "silver_s3" {
  name = "silver_s3"
}
