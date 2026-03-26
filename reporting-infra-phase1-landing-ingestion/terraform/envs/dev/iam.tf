data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_raw_ingest" {
  name_prefix        = "${var.project}-l-ing-"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "lambda_raw_ingest_logs" {
  role       = aws_iam_role.lambda_raw_ingest.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_raw_ingest_s3" {
  name_prefix = "s3-put-"
  role        = aws_iam_role.lambda_raw_ingest.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:PutObject", "s3:ListBucket"]
      Resource = [
        aws_s3_bucket.raw.arn,
        "${aws_s3_bucket.raw.arn}/*"
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_raw_ingest_pipeline_dynamo" {
  count      = var.enable_pipeline_dynamo ? 1 : 0
  role       = aws_iam_role.lambda_raw_ingest.name
  policy_arn = data.terraform_remote_state.dynamo_platform[0].outputs.iam_policy_pipeline_runs_arn
}

resource "aws_iam_role_policy" "lambda_raw_ingest_secrets" {
  name_prefix = "sm-"
  role        = aws_iam_role.lambda_raw_ingest.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = "arn:${data.aws_partition.current.partition}:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:reporting/*"
    }]
  })
}

# SFN 04: solo invocar Lambda de ingesta
resource "aws_iam_role" "sfn" {
  name_prefix = "${var.project}-sfn-p1-"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "states.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "sfn" {
  name_prefix = "invoke-ingest-"
  role        = aws_iam_role.sfn.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = aws_lambda_function.raw_ingest.arn
    }]
  })
}

resource "aws_iam_role" "events_sfn" {
  name_prefix = "${var.project}-ev-sfn-p1-"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "events_start_ingest_sfn" {
  name = "${local.name_prefix}-ev-ingest"
  role = aws_iam_role.events_sfn.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["states:StartExecution"]
      Resource = aws_sfn_state_machine.ingest_api_raw.arn
    }]
  })
}
