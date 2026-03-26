resource "random_id" "bucket_suffix" {
  byte_length = 2
}

resource "aws_s3_bucket" "raw" {
  bucket = "${local.name_prefix}-raw-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_notification" "raw_eventbridge" {
  count       = var.enable_s3_eventbridge_raw ? 1 : 0
  bucket      = aws_s3_bucket.raw.id
  eventbridge = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.s3_kms_key_arn != null ? "aws:kms" : "AES256"
      kms_master_key_id = var.s3_kms_key_arn
    }
    bucket_key_enabled = var.s3_kms_key_arn != null
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

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

  depends_on = [aws_s3_bucket_server_side_encryption_configuration.raw]
}

data "aws_iam_policy_document" "s3_deny_insecure_transport_raw" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions   = ["s3:*"]
    resources = [aws_s3_bucket.raw.arn, "${aws_s3_bucket.raw.arn}/*"]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "raw_deny_insecure" {
  bucket = aws_s3_bucket.raw.id
  policy = data.aws_iam_policy_document.s3_deny_insecure_transport_raw.json

  depends_on = [aws_s3_bucket_public_access_block.raw]
}
