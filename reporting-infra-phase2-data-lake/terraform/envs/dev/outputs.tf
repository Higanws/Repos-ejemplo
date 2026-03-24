output "s3_raw_bucket" {
  value       = data.aws_s3_bucket.raw.bucket
  description = "RAW (fase 1)."
}

output "s3_standardized_bucket" {
  value = aws_s3_bucket.standardized.bucket
}

output "s3_silver_bucket" {
  value = aws_s3_bucket.silver.bucket
}

output "s3_artifacts_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}

output "s3_athena_results_bucket" {
  value = aws_s3_bucket.athena_results.bucket
}

output "glue_job_validated_to_standardized_name" {
  value = aws_glue_job.validated_to_standardized.name
}

output "glue_job_validated_to_standardized_arn" {
  value = aws_glue_job.validated_to_standardized.arn
}

output "glue_job_standardized_to_silver_name" {
  value = aws_glue_job.standardized_to_silver.name
}

output "glue_job_standardized_to_silver_arn" {
  value = aws_glue_job.standardized_to_silver.arn
}

output "lambda_glue_schema_function_name" {
  value = aws_lambda_function.glue_schema.function_name
}

output "lambda_glue_schema_arn" {
  value = aws_lambda_function.glue_schema.arn
}

output "athena_workgroup_name" {
  value = aws_athena_workgroup.ddl.name
}

output "lambda_lake_pipeline_stream_router_arn" {
  value       = length(aws_lambda_function.lake_stream_router) > 0 ? aws_lambda_function.lake_stream_router[0].arn : null
  description = "Router fase 2 vía DynamoDB Stream; null si enable_pipeline_ddb_stream_chain es false."
}
