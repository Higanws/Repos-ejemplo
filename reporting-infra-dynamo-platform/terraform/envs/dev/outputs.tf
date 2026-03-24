output "dynamodb_table_name" {
  description = "Nombre de la tabla de corridas (pipeline_runs)."
  value       = aws_dynamodb_table.pipeline_runs.name
}

output "dynamodb_table_arn" {
  value = aws_dynamodb_table.pipeline_runs.arn
}

output "dynamodb_stream_arn" {
  description = "ARN del stream de pipeline_runs (routers por fase en 2/3)."
  value       = aws_dynamodb_table.pipeline_runs.stream_arn
}

output "dynamodb_gsi_name" {
  value = "gsi_env_business_date"
}

output "env_key" {
  description = "Valor literal env_key para ítems (ej. PIPE#reporting#dev)."
  value       = local.env_key
}

output "archive_bucket_name" {
  value = aws_s3_bucket.dynamo_archive.bucket
}

output "archive_bucket_arn" {
  value = aws_s3_bucket.dynamo_archive.arn
}

output "lambda_archive_function_name" {
  value = var.enable_archive_lambda ? aws_lambda_function.dynamo_archive[0].function_name : null
}

output "iam_policy_pipeline_runs_arn" {
  description = "ARN de la política IAM para adjuntar a roles de Lambdas de fases 1–3."
  value       = aws_iam_policy.pipeline_phases_dynamo.arn
}

output "ssm_parameter_table_name" {
  value = aws_ssm_parameter.pipeline_runs_table_name.name
}
