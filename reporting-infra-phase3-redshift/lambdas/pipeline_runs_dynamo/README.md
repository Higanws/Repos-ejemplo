# `pipeline_runs_dynamo`

| | |
|--|--|
| **Qué es** | Lambda **dedicada** (fase 3): DynamoDB `pipeline_runs` + validación de contratos silver en S3. Paralelo de diseño a `glue_job_status_dynamo` en fase 2. |
| **Disparo** | Invocación **síncrona** desde `redshift_sql` (`lambda:InvokeFunction`), no EventBridge. |
| **Qué no hace** | No ejecuta SQL en Redshift (eso es `redshift_sql`). No arranca Step Functions (eso es `redshift_sfn_stream_router`). |

## Contrato de invocación (`main.handler`)

Cuerpo JSON con `action`:

| `action` | Campos requeridos |
|----------|-------------------|
| `validate_silver_s3_for_copy` | `business_date`, `silver_bucket`, `art_bucket`; opcional `registry_key`, `contracts_root` |
| `require_previous_layer_for_redshift_script` | `script`, `project`, `env`, `business_date`, `batch_id` |
| `record_redshift_layer` | `project`, `env`, `business_date`, `batch_id`, `script`, `result_summary` |
| `record_redshift_layer_failed` | `project`, `env`, `business_date`, `batch_id`, `script`, `error` |

Respuesta OK: `{"ok": true}`.

## Variables de entorno (Terraform)

- `PIPELINE_RUNS_TABLE`, `ARTIFACTS_BUCKET`, `SILVER_BUCKET`, `PROJECT`, `ENVIRONMENT`
- `REDSHIFT_REGISTRY_KEY`, `REDSHIFT_CONTRACTS_ROOT`
- `PIPELINE_SKIP_LAYER_CHECK`, `PIPELINE_SKIP_CONTRACT_CHECK` (opcionales)
