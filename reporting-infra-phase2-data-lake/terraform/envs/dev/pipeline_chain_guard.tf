# enable_pipeline_ddb_stream_chain: routers por fase (lake en fase 2, Redshift en fase 3) leen el stream de pipeline_runs.

resource "terraform_data" "pipeline_chain_guard" {
  lifecycle {
    precondition {
      condition     = !var.enable_pipeline_ddb_stream_chain || var.enable_pipeline_dynamo
      error_message = "enable_pipeline_ddb_stream_chain requiere enable_pipeline_dynamo."
    }
  }
}
