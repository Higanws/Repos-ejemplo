resource "aws_iam_role" "redshift_s3" {
  name_prefix = "${var.project}-rs-s3-"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "redshift.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "redshift_s3" {
  name_prefix = "s3-access-"
  role        = aws_iam_role.redshift_s3.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          data.aws_s3_bucket.raw.arn,
          "${data.aws_s3_bucket.raw.arn}/*",
          data.aws_s3_bucket.standardized.arn,
          "${data.aws_s3_bucket.standardized.arn}/*",
          data.aws_s3_bucket.silver.arn,
          "${data.aws_s3_bucket.silver.arn}/*"
        ]
      }
    ]
  })
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_redshift_sql" {
  name_prefix        = "${var.project}-l-rs-"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "lambda_redshift_sql_logs" {
  role       = aws_iam_role.lambda_redshift_sql.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_redshift_sql_invoke_pipeline_runs" {
  count = var.enable_pipeline_dynamo ? 1 : 0
  name  = "invoke-pipeline-runs-dynamo"
  role  = aws_iam_role.lambda_redshift_sql.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.pipeline_runs_dynamo[0].arn
    }]
  })
}

resource "aws_iam_role_policy" "lambda_redshift_sql" {
  name_prefix = "data-api-"
  role        = aws_iam_role.lambda_redshift_sql.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "redshift-data:ExecuteStatement",
          "redshift-data:DescribeStatement",
          "redshift-data:GetStatementResult",
          "redshift-data:CancelStatement"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [local.redshift_data_api_secret_arn]
      },
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          data.aws_s3_bucket.artifacts.arn,
          "${data.aws_s3_bucket.artifacts.arn}/*"
        ]
      }
    ]
  })
}
