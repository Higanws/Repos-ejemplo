output "redshift_workgroup_name" {
  value = aws_redshiftserverless_workgroup.main.workgroup_name
}

output "redshift_namespace" {
  value = aws_redshiftserverless_namespace.main.namespace_name
}

output "redshift_database" {
  value = aws_redshiftserverless_namespace.main.db_name
}

output "redshift_admin_secret_arn" {
  value     = aws_redshiftserverless_namespace.main.admin_password_secret_arn
  sensitive = true
}

output "redshift_copy_iam_role_arn" {
  value = aws_iam_role.redshift_s3.arn
}

output "lambda_redshift_sql_function_name" {
  value = aws_lambda_function.redshift_sql.function_name
}

output "lambda_redshift_sql_arn" {
  value = aws_lambda_function.redshift_sql.arn
}

output "lambda_pipeline_runs_dynamo_function_name" {
  description = "Lambda dedicada Dynamo/contratos (null si enable_pipeline_dynamo=false)."
  value       = var.enable_pipeline_dynamo ? aws_lambda_function.pipeline_runs_dynamo[0].function_name : null
}

output "lambda_pipeline_runs_dynamo_arn" {
  description = "ARN de pipeline_runs_dynamo (null si enable_pipeline_dynamo=false)."
  value       = var.enable_pipeline_dynamo ? aws_lambda_function.pipeline_runs_dynamo[0].arn : null
}

output "pipeline_copy_state_machine_arn" {
  description = "Step Functions: cadena COPY (null si cadena deshabilitada o lista vacía)."
  value       = length(aws_sfn_state_machine.pipeline_copy) > 0 ? aws_sfn_state_machine.pipeline_copy[0].arn : null
}

output "pipeline_gold_state_machine_arn" {
  description = "Step Functions: cadena gold (null si cadena deshabilitada o lista vacía)."
  value       = length(aws_sfn_state_machine.pipeline_gold) > 0 ? aws_sfn_state_machine.pipeline_gold[0].arn : null
}

output "lambda_redshift_sfn_stream_router_arn" {
  description = "Lambda redshift_sfn_stream_router: stream → Step Functions COPY/gold. Null si cadena deshabilitada o sin scripts."
  value       = length(aws_lambda_function.redshift_sfn_stream_router) > 0 ? aws_lambda_function.redshift_sfn_stream_router[0].arn : null
}
