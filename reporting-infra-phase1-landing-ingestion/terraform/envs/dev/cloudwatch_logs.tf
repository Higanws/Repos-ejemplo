# Retención de logs de la Lambda de ingesta (sin esto, el log group se crea solo al primer invoke y no expira).
resource "aws_cloudwatch_log_group" "lambda_raw_ingest" {
  name              = "/aws/lambda/${local.name_prefix}-run-raw-api-ingestion"
  retention_in_days = var.lambda_log_retention_days

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}
