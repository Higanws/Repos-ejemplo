# Secreto para Bearer token (nombre debe coincidir con api_secret_name en config/{dev|test|prod}.json).
# Si ya creaste el secreto a mano en la consola, poné create_ingest_api_secret = false en tfvars.

resource "aws_secretsmanager_secret" "ingest_api" {
  count = var.create_ingest_api_secret ? 1 : 0

  name                    = var.ingest_api_secret_name
  recovery_window_in_days = 30 # ventana antes de borrado definitivo al destroy (prod)

  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

resource "aws_secretsmanager_secret_version" "ingest_api" {
  count = var.create_ingest_api_secret && var.ingest_api_secret_string != null ? 1 : 0

  secret_id     = aws_secretsmanager_secret.ingest_api[0].id
  secret_string = var.ingest_api_secret_string
}
