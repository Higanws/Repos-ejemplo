resource "aws_cloudwatch_event_rule" "ingest_schedule" {
  name                = "${local.name_prefix}-ingest-api-raw"
  description         = "Dispara SFN 04 ingesta API → RAW"
  schedule_expression = var.ingest_schedule_cron
}

resource "aws_cloudwatch_event_target" "ingest_sfn" {
  rule      = aws_cloudwatch_event_rule.ingest_schedule.name
  target_id = "SfnIngest"
  arn       = aws_sfn_state_machine.ingest_api_raw.arn
  role_arn  = aws_iam_role.events_sfn.arn
  input     = jsonencode({})
}
