resource "aws_s3_bucket" "dynamo_archive" {
  bucket = "${local.name_prefix}-dynamo-archive-${data.aws_caller_identity.current.account_id}"

  tags = {
    Project     = var.project
    Environment = var.environment
    Purpose     = "dynamodb-pipeline-runs-archive"
  }
}

resource "aws_s3_bucket_versioning" "dynamo_archive" {
  bucket = aws_s3_bucket.dynamo_archive.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "dynamo_archive" {
  bucket = aws_s3_bucket.dynamo_archive.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "dynamo_archive" {
  bucket = aws_s3_bucket.dynamo_archive.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_caller_identity" "current" {}
