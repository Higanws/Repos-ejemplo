# Fase 2 — Data lake (Glue + Athena + S3)

Repo **autocontenido**: lake en S3, catálogo Glue, Athena, jobs ETL y Lambda de esquemas; el código vive en `glue-data-lake/` y `lambdas/glue_schema_athena/`.

## Qué hace

| Recurso | Descripción |
|---------|-------------|
| S3 **standardized** / **silver** | Parquet por capa. |
| S3 **artifacts** | DDL Glue (desde `reporting-infra-schema-registry`) y SQL de jobs (desde este repo). |
| S3 **Athena results** | Resultados de consultas. |
| **Glue** | Catálogo y jobs ETL: leen **archivos** en landing (`validated/<dataset>/`) → **standardized** (Parquet) y **silver** (Parquet). Los nombres `trade_event` / `price_history` son **datasets** (prefijos S3), no tablas RAW en Glue. |
| **Athena** | Workgroup asociado al lake. |
| Lambda **glue_schema** | Ejecuta DDL en Athena/Glue a partir de scripts en artifacts. |

Los Spark SQL y scripts están bajo `glue-data-lake/`; los DDL de catálogo Glue se centralizan en `../reporting-infra-schema-registry/schemas/glue/`.

**Contratos de entrada** (por job Glue): [`glue-data-lake/contracts/registry.input.json`](glue-data-lake/contracts/registry.input.json) y `contracts/input/*.json`. Cada paso valida lo que **exige leer** desde la capa anterior antes de ejecutar; flujo end-to-end en [`../docs/ARQUITECTURA.md`](../docs/ARQUITECTURA.md).

**Cadena de capas:** con `enable_pipeline_ddb_stream_chain`, la Lambda **`lake_pipeline_stream_router`** consume el **DynamoDB Stream** de `pipeline_runs` y arranca los Glue cuando la capa previa queda OK en Dynamo. Redshift se dispara desde el router de fase 3. Las escrituras de estado en Dynamo para Glue están en `glue_job_status_dynamo` y en los jobs (`pipeline_layer_finish`).

## Dependencia

Lee **`terraform_remote_state` de la fase 1** (`phase1_state_*`). Aplicá primero `reporting-infra-phase1-landing-ingestion`.

## Terraform

```bash
cd terraform/envs/dev
cp terraform.tfvars.example terraform.tfvars
# Alinear remote_state / backend con el state de fase 1
terraform init
terraform apply
```

Opcional: `phase2_repository_root` en `tfvars`.
Si el repo de schemas no está como carpeta hermana, definir también `schema_registry_repository_root` en `tfvars`.

## Estructura (resumen)

```
glue-data-lake/
  sqls/                    # Spark SQL por job
  jobs/                    # Scripts Glue (Python)
  config/glue_pipeline.json
../reporting-infra-schema-registry/schemas/glue/
  standardized_s3/ silver_s3/  # DDL Glue/Athena (sin tablas "RAW": el RAW es S3)
lambdas/glue_schema_athena/
terraform/envs/dev/
```

## Siguiente

Fase 3 (Redshift) y guía de despliegue: [`../docs/TECNICO_DEPLOY.md`](../docs/TECNICO_DEPLOY.md)
