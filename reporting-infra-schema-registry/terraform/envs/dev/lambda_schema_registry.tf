data "archive_file" "zip_schema_registry_lambda" {
  type        = "zip"
  source_dir  = local.repo_root
  output_path = "${path.module}/.build/schema_registry_lambda.zip"
  excludes = [
    ".git/**",
    "terraform/**",
    "**/__pycache__/**",
    "**/*.pyc",
    ".idea/**",
    ".vscode/**"
  ]
}

resource "aws_iam_role" "schema_registry_lambda" {
  name = "${local.name_prefix}-schema-registry-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "schema_registry_lambda_logs" {
  role       = aws_iam_role.schema_registry_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "schema_registry_lambda_access" {
  name = "schema-registry-access"
  role = aws_iam_role.schema_registry_lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "glue:GetTable"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "redshift-data:ExecuteStatement",
          "redshift-data:DescribeStatement",
          "redshift-data:GetStatementResult"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = data.terraform_remote_state.phase3.outputs.redshift_admin_secret_arn
      }
    ]
  })
}

resource "aws_lambda_function" "schema_registry" {
  filename         = data.archive_file.zip_schema_registry_lambda.output_path
  function_name    = "${local.name_prefix}-schema-registry-apply"
  role             = aws_iam_role.schema_registry_lambda.arn
  handler          = "lambdas.schema_registry.main.handler"
  runtime          = "python3.12"
  timeout          = 900
  source_code_hash = data.archive_file.zip_schema_registry_lambda.output_base64sha256

  environment {
    variables = {
      STANDARDIZED_BUCKET = data.terraform_remote_state.phase2.outputs.s3_standardized_bucket
      SILVER_BUCKET       = data.terraform_remote_state.phase2.outputs.s3_silver_bucket
      ATHENA_WORKGROUP    = data.terraform_remote_state.phase2.outputs.athena_workgroup_name
      ATHENA_OUTPUT_S3    = local.athena_output_s3
      REDSHIFT_WORKGROUP  = data.terraform_remote_state.phase3.outputs.redshift_workgroup_name
      REDSHIFT_DATABASE   = data.terraform_remote_state.phase3.outputs.redshift_database
      REDSHIFT_SECRET_ARN = data.terraform_remote_state.phase3.outputs.redshift_admin_secret_arn
    }
  }
}

resource "aws_lambda_invocation" "invoke_on_apply" {
  count         = var.invoke_on_apply ? 1 : 0
  function_name = aws_lambda_function.schema_registry.function_name
  input = jsonencode({
    target          = var.invoke_target
    force_ddl       = var.invoke_force_ddl
    dry_run         = false
    deployment_hash = data.archive_file.zip_schema_registry_lambda.output_base64sha256
  })

  depends_on = [aws_lambda_function.schema_registry]
}
