output "s3_raw_bucket" {
  value       = aws_s3_bucket.raw.bucket
  description = "Nombre del bucket RAW (input phase2+)."
}

output "s3_raw_bucket_arn" {
  value = aws_s3_bucket.raw.arn
}

output "lambda_raw_ingest_function_name" {
  value = aws_lambda_function.raw_ingest.function_name
}

output "lambda_raw_ingest_arn" {
  value = aws_lambda_function.raw_ingest.arn
}

output "sfn_ingest_api_raw_arn" {
  value = aws_sfn_state_machine.ingest_api_raw.arn
}

output "sfn_ingest_api_raw_name" {
  value = aws_sfn_state_machine.ingest_api_raw.name
}

output "ingest_api_secret_arn" {
  value       = length(aws_secretsmanager_secret.ingest_api) > 0 ? aws_secretsmanager_secret.ingest_api[0].arn : null
  description = "ARN del secreto Bearer (null si create_ingest_api_secret = false)."
}
