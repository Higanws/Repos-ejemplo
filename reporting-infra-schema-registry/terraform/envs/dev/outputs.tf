output "lambda_schema_registry_function_name" {
  value = aws_lambda_function.schema_registry.function_name
}

output "lambda_schema_registry_arn" {
  value = aws_lambda_function.schema_registry.arn
}
