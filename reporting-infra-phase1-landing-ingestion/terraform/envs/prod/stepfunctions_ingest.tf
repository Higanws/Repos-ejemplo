locals {
  sfn_def_04 = replace(
    file("${local.phase1_repo_root}/orchestration/pipelines/04_ingesta_api_raw.json"),
    "__RAW_INGEST_LAMBDA__",
    aws_lambda_function.raw_ingest.function_name
  )
}

resource "aws_sfn_state_machine" "ingest_api_raw" {
  name       = "${local.name_prefix}-04-ingest-api-raw"
  role_arn   = aws_iam_role.sfn.arn
  definition = local.sfn_def_04

  depends_on = [aws_iam_role_policy.sfn]
}
