locals {
  rs_ddl_files      = fileset("${local.redshift_schema_registry_root}", "**/*.sql")
  rs_job_files      = fileset("${local.redshift_embed_root}", "jobs-sql/**/*.sql")
  rs_contract_files = fileset("${local.redshift_embed_root}", "contracts/**/*.json")
}

resource "aws_s3_object" "redshift_ddl" {
  for_each = { for f in local.rs_ddl_files : f => f }

  bucket = data.aws_s3_bucket.artifacts.bucket
  key    = "sql/${each.value}"
  source = "${local.redshift_schema_registry_root}/${each.value}"
  etag   = filemd5("${local.redshift_schema_registry_root}/${each.value}")
}

resource "aws_s3_object" "redshift_jobs_sql" {
  for_each = { for f in local.rs_job_files : f => f }

  bucket = data.aws_s3_bucket.artifacts.bucket
  key    = "sql/${trimprefix(each.value, "jobs-sql/")}"
  source = "${local.redshift_embed_root}/${each.value}"
  etag   = filemd5("${local.redshift_embed_root}/${each.value}")
}

resource "aws_s3_object" "redshift_contracts" {
  for_each = { for f in local.rs_contract_files : f => f }

  bucket = data.aws_s3_bucket.artifacts.bucket
  key    = "redshift/${each.value}"
  source = "${local.redshift_embed_root}/${each.value}"
  etag   = filemd5("${local.redshift_embed_root}/${each.value}")
}
