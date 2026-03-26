resource "terraform_data" "pipeline_chain_guard" {
  lifecycle {
    precondition {
      condition     = !var.enable_pipeline_ddb_stream_chain || var.enable_pipeline_dynamo
      error_message = "enable_pipeline_ddb_stream_chain requiere enable_pipeline_dynamo."
    }
  }
}
