# `redshift_sfn_stream_router`

| | |
|--|--|
| **Qué es** | Lambda **router** de la fase 3: reacciona al **DynamoDB Stream** de `pipeline_runs`. |
| **Qué hace** | Si `lake_standardized_to_silver` → `SUCCEEDED`, arranca la SFN **COPY**. Si `redshift_silver` → `SUCCEEDED`, arranca la SFN **gold**. |
| **Qué no hace** | No ejecuta SQL (eso es `redshift_sql`). No escribe Dynamo (eso es la Lambda `pipeline_runs_dynamo`, invocada por `redshift_sql`). |

Estructura alineada con fase 2: carpeta propia junto a `redshift_sql/` y `pipeline_runs_dynamo/` (estado Dynamo empaquetado en el zip de `redshift_sql`), como allí `lake_pipeline_stream_router/` junto a `glue_job_status_dynamo/`.

## Variables de entorno (Terraform)

- `PIPELINE_COPY_STATE_MACHINE_ARN` — SFN que orquesta los `.sql` de COPY.
- `PIPELINE_GOLD_STATE_MACHINE_ARN` — SFN que orquesta los `.sql` de gold.
- `PROJECT`, `ENVIRONMENT`, `PIPELINE_RUNS_TABLE` (informativo; el trigger es el stream).

## Nombre en AWS

La función se despliega como `{project}-{environment}-redshift-sfn-stream-router` (ver Terraform).
