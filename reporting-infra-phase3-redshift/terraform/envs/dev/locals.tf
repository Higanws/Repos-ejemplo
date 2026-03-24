locals {
  phase3_repo_root = coalesce(var.phase3_repository_root, abspath("${path.module}/../../.."))
  schema_registry_repo_root = coalesce(
    var.schema_registry_repository_root,
    abspath("${local.phase3_repo_root}/../reporting-infra-schema-registry")
  )

  name_prefix = "${var.project}-${var.environment}"

  redshift_embed_root = "${local.phase3_repo_root}/redshift"
  redshift_schema_registry_root = "${local.schema_registry_repo_root}/schemas/redshift"

  redshift_data_api_secret_arn = coalesce(
    var.redshift_sql_secret_arn,
    aws_redshiftserverless_namespace.main.admin_password_secret_arn
  )

  # redshift_sql: solo SQL; PIPELINE_SKIP_* aquí evita invocar a pipeline_runs_dynamo cuando corresponde.
  lambda_redshift_sql_env = merge(
    {
      ARTIFACTS_BUCKET      = data.aws_s3_bucket.artifacts.bucket
      SILVER_BUCKET         = data.aws_s3_bucket.silver.bucket
      REDSHIFT_WORKGROUP    = aws_redshiftserverless_workgroup.main.workgroup_name
      REDSHIFT_DATABASE     = aws_redshiftserverless_namespace.main.db_name
      REDSHIFT_SECRET_ARN   = local.redshift_data_api_secret_arn
      REDSHIFT_IAM_ROLE_ARN = aws_iam_role.redshift_s3.arn
      PROJECT               = var.project
      ENVIRONMENT           = var.environment
    },
    var.enable_pipeline_dynamo ? merge(
      {
        PIPELINE_RUNS_LAMBDA_NAME = aws_lambda_function.pipeline_runs_dynamo[0].function_name
        REDSHIFT_REGISTRY_KEY     = "redshift/contracts/registry.input.json"
        REDSHIFT_CONTRACTS_ROOT   = "redshift/contracts"
      },
      var.pipeline_skip_layer_check ? { PIPELINE_SKIP_LAYER_CHECK = "true" } : {},
      var.pipeline_skip_contract_check ? { PIPELINE_SKIP_CONTRACT_CHECK = "true" } : {}
    ) : {}
  )
}
