resource "random_id" "bucket_suffix" {
  byte_length = 2
}

resource "aws_s3_bucket" "silver" {
  bucket = "${local.name_prefix}-silver-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket" "standardized" {
  bucket = "${local.name_prefix}-standardized-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket" "artifacts" {
  bucket = "${local.name_prefix}-artifacts-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket" "athena_results" {
  bucket = "${local.name_prefix}-athena-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "silver" {
  bucket                  = aws_s3_bucket.silver.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "standardized" {
  bucket                  = aws_s3_bucket.standardized.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "athena_results" {
  bucket                  = aws_s3_bucket.athena_results.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_notification" "artifacts_eventbridge" {
  bucket      = aws_s3_bucket.artifacts.id
  eventbridge = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "managed" {
  for_each = local.s3_managed_buckets
  bucket   = each.value.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.s3_kms_key_arn != null ? "aws:kms" : "AES256"
      kms_master_key_id = var.s3_kms_key_arn
    }
    bucket_key_enabled = var.s3_kms_key_arn != null
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data_lake" {
  for_each = toset(["standardized", "silver"])
  bucket   = local.s3_managed_buckets[each.key].id

  rule {
    id     = "default"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = var.s3_abort_multipart_days
    }

    dynamic "transition" {
      for_each = var.s3_transition_current_to_ia_days != null ? [var.s3_transition_current_to_ia_days] : []
      content {
        days          = transition.value
        storage_class = "STANDARD_IA"
      }
    }

    filter {}
  }

  depends_on = [aws_s3_bucket_server_side_encryption_configuration.managed]
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts_and_athena" {
  for_each = toset(["artifacts", "athena"])
  bucket   = local.s3_managed_buckets[each.key].id

  rule {
    id     = "abort-mpu"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = var.s3_abort_multipart_days
    }

    filter {}
  }

  depends_on = [aws_s3_bucket_server_side_encryption_configuration.managed]
}

data "aws_iam_policy_document" "s3_deny_insecure_transport" {
  for_each = local.s3_managed_buckets

  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions   = ["s3:*"]
    resources = [each.value.arn, "${each.value.arn}/*"]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "deny_insecure_transport" {
  for_each = local.s3_managed_buckets
  bucket   = each.value.id
  policy   = data.aws_iam_policy_document.s3_deny_insecure_transport[each.key].json

  depends_on = [
    aws_s3_bucket_public_access_block.silver,
    aws_s3_bucket_public_access_block.standardized,
    aws_s3_bucket_public_access_block.artifacts,
    aws_s3_bucket_public_access_block.athena_results,
  ]
}
