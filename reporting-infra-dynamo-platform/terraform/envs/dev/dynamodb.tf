resource "aws_dynamodb_table" "pipeline_runs" {
  name         = "${local.name_prefix}-pipeline-runs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "env_key"
    type = "S"
  }

  attribute {
    name = "business_date"
    type = "S"
  }

  global_secondary_index {
    name            = "gsi_env_business_date"
    hash_key        = "env_key"
    range_key       = "business_date"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  # Routers por fase (Lambdas en fase 2/3) consumen el stream para encadenar sin mezclar responsabilidades.
  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  tags = {
    Project     = var.project
    Environment = var.environment
    Purpose     = "pipeline-run-state"
  }
}
