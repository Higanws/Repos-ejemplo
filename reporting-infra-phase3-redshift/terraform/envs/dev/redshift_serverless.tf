resource "aws_redshiftserverless_namespace" "main" {
  namespace_name        = "${local.name_prefix}-ns"
  db_name               = "reporting"
  admin_username        = "admin"
  manage_admin_password = true
  default_iam_role_arn  = aws_iam_role.redshift_s3.arn
  iam_roles             = [aws_iam_role.redshift_s3.arn]
}

resource "aws_redshiftserverless_workgroup" "main" {
  namespace_name      = aws_redshiftserverless_namespace.main.namespace_name
  workgroup_name      = "${local.name_prefix}-wg"
  base_capacity       = var.redshift_base_capacity
  subnet_ids          = length(data.aws_subnets.default.ids) > 3 ? slice(data.aws_subnets.default.ids, 0, 3) : data.aws_subnets.default.ids
  security_group_ids  = [aws_security_group.redshift.id]
  publicly_accessible = var.redshift_publicly_accessible

  depends_on = [aws_redshiftserverless_namespace.main]
}
