data "aws_iam_policy_document" "lambda_archive_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_archive" {
  count              = var.enable_archive_lambda ? 1 : 0
  name               = "${local.name_prefix}-dynamo-archive-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_archive_assume.json
}

resource "aws_iam_role_policy_attachment" "lambda_archive_basic" {
  count      = var.enable_archive_lambda ? 1 : 0
  role       = aws_iam_role.lambda_archive[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "lambda_archive_inline" {
  statement {
    sid = "DynamoQueryDelete"
    actions = [
      "dynamodb:Query",
      "dynamodb:DeleteItem",
    ]
    resources = [
      aws_dynamodb_table.pipeline_runs.arn,
      "${aws_dynamodb_table.pipeline_runs.arn}/index/*",
    ]
  }

  statement {
    sid = "S3ArchiveWrite"
    actions = [
      "s3:PutObject",
    ]
    resources = ["${aws_s3_bucket.dynamo_archive.arn}/*"]
  }
}

resource "aws_iam_role_policy" "lambda_archive" {
  count  = var.enable_archive_lambda ? 1 : 0
  name   = "dynamo-archive-dynamo-s3"
  role   = aws_iam_role.lambda_archive[0].id
  policy = data.aws_iam_policy_document.lambda_archive_inline.json
}

# Política para que las Lambdas de fases 1–3 (adjuntar manualmente o por TF en cada repo) puedan leer/escribir estado.
data "aws_iam_policy_document" "pipeline_phases_dynamo" {
  statement {
    sid = "PipelineRunsRW"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:Query",
      "dynamodb:BatchWriteItem",
    ]
    resources = [
      aws_dynamodb_table.pipeline_runs.arn,
      "${aws_dynamodb_table.pipeline_runs.arn}/index/*",
    ]
  }
}

resource "aws_iam_policy" "pipeline_phases_dynamo" {
  name         = "${local.name_prefix}-pipeline-runs-access"
  description  = "Adjuntar a roles de Lambdas de ingesta/lake/redshift para estado de corridas."
  policy       = data.aws_iam_policy_document.pipeline_phases_dynamo.json
}
