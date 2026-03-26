locals {
  # terraform/envs/prod -> ../../.. = raíz de ESTE repo (landing + ingesta).
  phase1_repo_root = coalesce(var.phase1_repository_root, abspath("${path.module}/../../.."))

  name_prefix = "${var.project}-${var.environment}"
}
