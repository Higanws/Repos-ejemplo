# Cadena Redshift (COPY + gold) como Step Functions: un Task por .sql, misma Lambda redshift_sql.
# Quién arranca la SFN: Lambda redshift_sfn_stream_router (lee el stream de pipeline_runs).

locals {
  copy_scripts = compact([for s in split(",", var.pipeline_copy_scripts_order) : trimspace(s)])
  gold_scripts   = compact([for s in split(",", var.pipeline_gold_scripts_order) : trimspace(s)])
  copy_step_ids  = [for i, s in local.copy_scripts : "CopyStep${i}"]
  gold_step_ids  = [for i, s in local.gold_scripts : "GoldStep${i}"]
  pipeline_chain_enabled = var.enable_pipeline_ddb_stream_chain
}

resource "aws_iam_role" "sfn_pipeline" {
  count = local.pipeline_chain_enabled ? 1 : 0
  name  = "${local.name_prefix}-pipeline-sfn"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "states.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "sfn_invoke_redshift_sql" {
  count = local.pipeline_chain_enabled ? 1 : 0
  name  = "invoke-redshift-sql"
  role  = aws_iam_role.sfn_pipeline[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = [aws_lambda_function.redshift_sql.arn]
    }]
  })
}

locals {
  sfn_retry = [
    {
      ErrorEquals = [
        "Lambda.ServiceException",
        "Lambda.AWSLambdaException",
        "Lambda.SdkClientException",
        "Lambda.TooManyRequestsException"
      ]
      IntervalSeconds = 3
      MaxAttempts     = 3
      BackoffRate     = 2
    }
  ]
}

locals {
  copy_states = length(local.copy_scripts) > 0 ? merge([
    for i, sc in local.copy_scripts : {
      (local.copy_step_ids[i]) = merge(
        {
          Type     = "Task"
          Resource = "arn:aws:states:::lambda:invoke"
          Parameters = {
            FunctionName = aws_lambda_function.redshift_sql.arn
            Payload = merge(
              { script = sc },
              {
                "load_date.$"    = "$.load_date"
                "session_date.$" = "$.load_date"
                "batch_id.$"     = "$.batch_id"
              }
            )
          }
          ResultPath = "$.lastTask"
          Retry      = local.sfn_retry
        },
        i < length(local.copy_scripts) - 1 ? { Next = local.copy_step_ids[i + 1] } : { End = true }
      )
    }
  ]...) : {}
  gold_states = length(local.gold_scripts) > 0 ? merge([
    for i, sc in local.gold_scripts : {
      (local.gold_step_ids[i]) = merge(
        {
          Type     = "Task"
          Resource = "arn:aws:states:::lambda:invoke"
          Parameters = {
            FunctionName = aws_lambda_function.redshift_sql.arn
            Payload = merge(
              { script = sc },
              {
                "load_date.$"    = "$.load_date"
                "session_date.$" = "$.load_date"
                "batch_id.$"     = "$.batch_id"
              }
            )
          }
          ResultPath = "$.lastTask"
          Retry      = local.sfn_retry
        },
        i < length(local.gold_scripts) - 1 ? { Next = local.gold_step_ids[i + 1] } : { End = true }
      )
    }
  ]...) : {}
}

resource "aws_sfn_state_machine" "pipeline_copy" {
  count = local.pipeline_chain_enabled && length(local.copy_scripts) > 0 ? 1 : 0
  name  = "${local.name_prefix}-pipeline-copy-silver"
  role_arn = aws_iam_role.sfn_pipeline[0].arn

  definition = jsonencode({
    Comment = "COPY desde Silver S3 a Redshift (un paso por script SQL)"
    StartAt = local.copy_step_ids[0]
    States  = local.copy_states
  })

  depends_on = [aws_iam_role_policy.sfn_invoke_redshift_sql]
}

resource "aws_sfn_state_machine" "pipeline_gold" {
  count = local.pipeline_chain_enabled && length(local.gold_scripts) > 0 ? 1 : 0
  name  = "${local.name_prefix}-pipeline-silver-to-gold"
  role_arn = aws_iam_role.sfn_pipeline[0].arn

  definition = jsonencode({
    Comment = "Silver Redshift a Gold (un paso por script SQL)"
    StartAt = local.gold_step_ids[0]
    States  = local.gold_states
  })

  depends_on = [aws_iam_role_policy.sfn_invoke_redshift_sql]
}

resource "aws_lambda_permission" "sfn_copy_invoke_redshift_sql" {
  count         = local.pipeline_chain_enabled && length(local.copy_scripts) > 0 ? 1 : 0
  statement_id  = "AllowStepFunctionsPipelineCopy"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.redshift_sql.function_name
  principal     = "states.amazonaws.com"
  source_arn    = aws_sfn_state_machine.pipeline_copy[0].arn
}

resource "aws_lambda_permission" "sfn_gold_invoke_redshift_sql" {
  count         = local.pipeline_chain_enabled && length(local.gold_scripts) > 0 ? 1 : 0
  statement_id  = "AllowStepFunctionsPipelineGold"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.redshift_sql.function_name
  principal     = "states.amazonaws.com"
  source_arn    = aws_sfn_state_machine.pipeline_gold[0].arn
}
