resource "aws_iam_role" "glue_job" {
  name_prefix = "${var.project}-glue-"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "glue.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_job.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "glue_s3" {
  name_prefix = "s3-"
  role        = aws_iam_role.glue_job.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"
        ]
        Resource = [
          data.aws_s3_bucket.raw.arn,
          "${data.aws_s3_bucket.raw.arn}/*",
          aws_s3_bucket.standardized.arn,
          "${aws_s3_bucket.standardized.arn}/*",
          aws_s3_bucket.silver.arn,
          "${aws_s3_bucket.silver.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.artifacts.arn,
          "${aws_s3_bucket.artifacts.arn}/glue-sql/*",
          "${aws_s3_bucket.artifacts.arn}/glue-scripts/*",
          "${aws_s3_bucket.artifacts.arn}/glue-data-lake/*"
        ]
      }
    ]
  })
}

# Cada job Glue escribe su capa en Dynamo al terminar OK.
resource "aws_iam_role_policy_attachment" "glue_pipeline_runs_rw" {
  count      = var.enable_pipeline_dynamo ? 1 : 0
  role       = aws_iam_role.glue_job.name
  policy_arn = data.terraform_remote_state.dynamo_platform[0].outputs.iam_policy_pipeline_runs_arn
}

resource "aws_iam_role_policy" "glue_get_job_runs" {
  count = var.enable_pipeline_dynamo ? 1 : 0
  name  = "glue-get-job-runs-finish"
  role  = aws_iam_role.glue_job.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["glue:GetJobRuns"]
      Resource = "*"
    }]
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

resource "aws_iam_role" "lambda_glue_schema" {
  name_prefix        = "${var.project}-l-glue-"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "lambda_glue_schema_logs" {
  role       = aws_iam_role.lambda_glue_schema.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_glue_schema" {
  name_prefix = "athena-s3-"
  role        = aws_iam_role.lambda_glue_schema.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:StopQueryExecution",
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:GetTable",
          "glue:GetTables"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.artifacts.arn,
          "${aws_s3_bucket.artifacts.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"]
        Resource = [
          aws_s3_bucket.athena_results.arn,
          "${aws_s3_bucket.athena_results.arn}/*"
        ]
      }
    ]
  })
}
