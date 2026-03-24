locals {
  glue_ddl_files       = fileset("${local.glue_schema_registry_root}/glue", "**/*.sql")
  glue_spark_sql_files = fileset("${local.glue_data_lake_root}", "sqls/**/*.sql")
  glue_contract_files  = fileset("${local.glue_data_lake_root}/contracts", "**/*.json")
}

resource "aws_s3_object" "glue_ddl" {
  for_each = { for f in local.glue_ddl_files : f => f }

  bucket = aws_s3_bucket.artifacts.bucket
  key    = "glue-ddl/${trimprefix(each.value, "glue/")}"
  source = "${local.glue_schema_registry_root}/${each.value}"
  etag   = filemd5("${local.glue_schema_registry_root}/${each.value}")
}

resource "aws_s3_object" "glue_spark_sql" {
  for_each = { for f in local.glue_spark_sql_files : f => f }

  bucket = aws_s3_bucket.artifacts.bucket
  key    = "glue-sql/sqls/${trimprefix(each.value, "sqls/")}"
  source = "${local.glue_data_lake_root}/${each.value}"
  etag   = filemd5("${local.glue_data_lake_root}/${each.value}")
}

resource "aws_s3_object" "glue_pipeline_config" {
  bucket = aws_s3_bucket.artifacts.bucket
  key    = "glue-sql/config/glue_pipeline.json"
  source = "${local.glue_data_lake_root}/config/glue_pipeline.json"
  etag   = filemd5("${local.glue_data_lake_root}/config/glue_pipeline.json")
}

resource "aws_s3_object" "glue_contracts" {
  for_each = { for f in local.glue_contract_files : f => f }

  bucket = aws_s3_bucket.artifacts.bucket
  key    = "glue-data-lake/contracts/${each.value}"
  source = "${local.glue_data_lake_root}/contracts/${each.value}"
  etag   = filemd5("${local.glue_data_lake_root}/contracts/${each.value}")
}

resource "aws_s3_object" "pipeline_layer_gate" {
  bucket = aws_s3_bucket.artifacts.bucket
  key    = "glue-scripts/jobs/pipeline_layer_gate.py"
  source = "${local.glue_data_lake_root}/jobs/pipeline_layer_gate.py"
  etag   = filemd5("${local.glue_data_lake_root}/jobs/pipeline_layer_gate.py")
}

resource "aws_s3_object" "pipeline_contract_validate" {
  bucket = aws_s3_bucket.artifacts.bucket
  key    = "glue-scripts/jobs/pipeline_contract_validate.py"
  source = "${local.glue_data_lake_root}/jobs/pipeline_contract_validate.py"
  etag   = filemd5("${local.glue_data_lake_root}/jobs/pipeline_contract_validate.py")
}

resource "aws_s3_object" "pipeline_layer_finish" {
  bucket = aws_s3_bucket.artifacts.bucket
  key    = "glue-scripts/jobs/pipeline_layer_finish.py"
  source = "${local.glue_data_lake_root}/jobs/pipeline_layer_finish.py"
  etag   = filemd5("${local.glue_data_lake_root}/jobs/pipeline_layer_finish.py")
}

resource "aws_s3_object" "glue_script_validated_to_standardized" {
  bucket = aws_s3_bucket.artifacts.bucket
  key    = "glue-scripts/jobs/validated_to_standardized.py"
  content = replace(
    replace(
      file("${local.glue_data_lake_root}/jobs/validated_to_standardized.py"),
      "__RAW_BUCKET__",
      data.aws_s3_bucket.raw.bucket
    ),
    "__STANDARDIZED_BUCKET__",
    aws_s3_bucket.standardized.bucket
  )
  etag = md5(replace(
    replace(
      file("${local.glue_data_lake_root}/jobs/validated_to_standardized.py"),
      "__RAW_BUCKET__",
      data.aws_s3_bucket.raw.bucket
    ),
    "__STANDARDIZED_BUCKET__",
    aws_s3_bucket.standardized.bucket
  ))
}

resource "aws_s3_object" "glue_script_standardized_to_silver" {
  bucket = aws_s3_bucket.artifacts.bucket
  key    = "glue-scripts/jobs/standardized_to_silver.py"
  content = replace(
    replace(
      file("${local.glue_data_lake_root}/jobs/standardized_to_silver.py"),
      "__STANDARDIZED_BUCKET__",
      aws_s3_bucket.standardized.bucket
    ),
    "__SILVER_BUCKET__",
    aws_s3_bucket.silver.bucket
  )
  etag = md5(replace(
    replace(
      file("${local.glue_data_lake_root}/jobs/standardized_to_silver.py"),
      "__STANDARDIZED_BUCKET__",
      aws_s3_bucket.standardized.bucket
    ),
    "__SILVER_BUCKET__",
    aws_s3_bucket.silver.bucket
  ))
}
