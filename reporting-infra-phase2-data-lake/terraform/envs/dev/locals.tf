locals {
  # terraform/envs/dev -> ../../.. = raíz de ESTE repo (data lake autocontenido).
  phase2_repo_root = coalesce(var.phase2_repository_root, abspath("${path.module}/../../.."))
  schema_registry_repo_root = coalesce(
    var.schema_registry_repository_root,
    abspath("${local.phase2_repo_root}/../reporting-infra-schema-registry")
  )

  name_prefix = "${var.project}-${var.environment}"

  # Código Glue / catálogo embebido (sin monorepo 03/05/01).
  glue_data_lake_root = "${local.phase2_repo_root}/glue-data-lake"
  glue_schema_registry_root = "${local.schema_registry_repo_root}/schemas"

  s3_managed_buckets = {
    standardized = aws_s3_bucket.standardized
    silver       = aws_s3_bucket.silver
    artifacts    = aws_s3_bucket.artifacts
    athena       = aws_s3_bucket.athena_results
  }
}
