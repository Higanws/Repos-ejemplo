resource "terraform_data" "pipeline_chain_guard" {
  lifecycle {
    precondition {
      condition     = !var.enable_pipeline_ddb_stream_chain || var.enable_pipeline_dynamo
      error_message = "enable_pipeline_ddb_stream_chain requiere enable_pipeline_dynamo."
    }
    precondition {
      condition = !var.enable_pipeline_ddb_stream_chain || (
        length(compact([for s in split(",", var.pipeline_copy_scripts_order) : trimspace(s)])) > 0 ||
        length(compact([for s in split(",", var.pipeline_gold_scripts_order) : trimspace(s)])) > 0
      )
      error_message = "enable_pipeline_ddb_stream_chain requiere al menos un script COPY o gold."
    }
  }
}
