# `lake_pipeline_stream_router`

| | |
|--|--|
| **Qué es** | Lambda **router** de la fase 2 (data lake). |
| **Qué hace** | Consume el **DynamoDB Stream** de `pipeline_runs`. Cuando `raw` o `lake_validated_to_standardized` pasan a `SUCCEEDED`, llama a `glue:StartJobRun` para el siguiente job Glue. |
| **Qué no hace** | No escribe el estado Glue en Dynamo (eso es `glue_job_status_dynamo` y `pipeline_layer_finish` en los jobs). No toca Redshift (fase 3: `redshift_sfn_stream_router`). |

## Variables de entorno (Terraform)

- `GLUE_JOB_VALIDATED_TO_STD_NAME`, `GLUE_JOB_STD_TO_SILVER_NAME`
- `PROJECT`, `ENVIRONMENT`, `PIPELINE_RUNS_TABLE`
