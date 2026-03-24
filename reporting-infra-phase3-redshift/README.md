# Fase 3 — Redshift

Repo **autocontenido**: Redshift Serverless, rol IAM para **COPY** desde S3 silver, Lambda **`redshift_sql`** y sincronización de SQL al bucket **artifacts** de la fase 2.

## Qué hace

| Recurso | Descripción |
|---------|-------------|
| **Redshift Serverless** | Namespace + workgroup para analítica. |
| **Rol IAM** | Permite COPY desde el bucket silver / artifacts. |
| Lambda **redshift_sql** | Ejecuta SQL vía Data API. |
| Lambda **`pipeline_runs_dynamo`** | **Solo** DynamoDB `pipeline_runs` + validación contratos S3 (invocada por `redshift_sql`); mismo patrón que `glue_job_status_dynamo` en fase 2 (Lambda propia, zip propio). |
| **Objetos S3** | Terraform sube DDL desde `reporting-infra-schema-registry/schemas/redshift/**` y jobs desde `redshift/jobs-sql/**` a prefijos `sql/...` esperados por las SFN. |
| Lambda **`redshift_sfn_stream_router`** (opcional) | Router de fase 3: mismo **DynamoDB Stream** que en lake; al pasar `lake_standardized_to_silver` / `redshift_silver` a SUCCEEDED arranca la SFN **COPY** o **gold**. Código en `lambdas/redshift_sfn_stream_router/`. |

Rutas locales:

- `redshift/jobs-sql/copy_s3_to_silver/`, `silver_to_gold/` → `sql/copy_s3_to_silver/...`, `sql/silver_to_gold/...`
- `../reporting-infra-schema-registry/schemas/redshift/silver/`, `gold/` → `sql/silver/...`, `sql/gold/...`

## Dependencia

**Terraform remote state** de **fase 1** y **fase 2** (bucket RAW + lake/artifacts).

## Terraform

```bash
cd terraform/envs/dev
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

Opcional: `phase3_repository_root` en `tfvars`.
Si el repo de schemas no está como carpeta hermana, definir también `schema_registry_repository_root` en `tfvars`.

## Contratos de entrada (COPY / silver)

- [`redshift/contracts/registry.input.json`](redshift/contracts/registry.input.json) y `contracts/input/*.json` describen qué se espera desde **S3 silver** antes de ejecutar cada script (alinear con DDL centralizado).

## Estructura (resumen)

Alineada con fase 2: **una carpeta por Lambda** bajo `lambdas/` (router separado del ejecutor SQL).

```
redshift/jobs-sql/                 # COPY desde Parquet, agregados gold
redshift/contracts/                # registry + contratos de entrada por carga
../reporting-infra-schema-registry/schemas/redshift/
  silver/ gold/                    # DDL centralizados de Redshift
lambdas/redshift_sql/              # Ejecutor SQL (Data API)
lambdas/pipeline_runs_dynamo/      # Estado pipeline en Dynamo + contratos silver (invocada por redshift_sql)
lambdas/redshift_sfn_stream_router/  # Router: stream → Step Functions (COPY / gold)
terraform/envs/dev/
```

Ver `lambdas/redshift_sfn_stream_router/README.md` para detalle del router.

## ¿Funciona este diseño en AWS?

Sí, con los matices habituales de producción:

- **DynamoDB Streams** + **dos Lambdas** (lake y Redshift) como consumidores del mismo stream está [soportado](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html): cada mapping tiene su propio cursor por shard.
- **Orden:** el orden se mantiene por clave de partición del stream; conviene que `batch_id` + `business_date` identifiquen bien la corrida.
- **Reintentos:** Lambda puede reinvocar con el mismo batch; el router debe ser tolerante (transición “no SUCCEEDED” → “SUCCEEDED” ya está cubierta por `_just_succeeded`).
- **Despliegue:** aplicar **dynamo-platform** (stream en la tabla + output `dynamodb_stream_arn`), luego fase 3 (SFN + router), luego fase 2 (router lake), para que los ARNs de SFN existan antes del router Redshift.

Si falta stream en la tabla o permisos IAM en el rol de la Lambda, el `event_source_mapping` fallará en `terraform apply`.

## Guía de orden de deploy

[`../docs/TECNICO_DEPLOY.md`](../docs/TECNICO_DEPLOY.md) · Arquitectura y capas: [`../docs/ARQUITECTURA.md`](../docs/ARQUITECTURA.md)
