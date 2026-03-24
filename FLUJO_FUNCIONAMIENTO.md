# Flujo esperado de funcionamiento V1 (AWS)

Este documento resume **como debe funcionar el pipeline** con la logica actual definida para los repos.

## 1) Principio general

La plataforma funciona por **capas encadenadas por eventos**, no por un orquestador monolitico:

1. Fase 1 ingiere y valida.
2. Fase 2 procesa en Glue (2 capas).
3. Fase 3 ejecuta SQL en Redshift con Step Functions (un `.sql` por estado).
4. DynamoDB guarda el estado de corrida por `business_date`/`batch_id`.
5. El **stream** de esa tabla y los **routers por fase** (lake en fase 2, Redshift en fase 3) disparan la siguiente Glue o Step Function cuando la capa anterior queda OK en Dynamo.

## 2) Repos y responsabilidades

- `reporting-infra-dynamo-platform`
  - Tabla `pipeline_runs`, IAM compartido y archivado historico.
- `reporting-infra-phase1-landing-ingestion`
  - Ingesta API -> **bucket S3 RAW** en prefijos `validated/` o `rejected/` (mismo bucket, distinto prefijo).
- `reporting-infra-phase2-data-lake`
  - Glue `validated_to_standardized` y `standardized_to_silver`.
  - Lambdas de estado/router/catalogo (`glue_job_status_dynamo`, `lake_pipeline_stream_router`, `glue_schema_athena`).
- `reporting-infra-phase3-redshift`
  - Lambda `redshift_sql` + Step Functions COPY/gold.
- `reporting-infra-schema-registry`
  - Fuente central de DDL para Glue/Athena y Redshift (ejecución on-demand).

## 2.1) Estructura de carpetas por repo (V1)

### `reporting-infra-dynamo-platform`

- `terraform/`
  - Infra de tabla DynamoDB, S3 de archivo, Lambda de archivado, IAM y outputs.
- `lambdas/`
  - Codigo de la Lambda de archivado programado.
- `docs/`
  - Esquema de item y reglas de consulta (`DYNAMODB_SCHEMA.md`).

### `reporting-infra-phase1-landing-ingestion`

- `terraform/`
  - Bucket RAW, Lambda ingesta, Step Functions de ingesta y EventBridge cron.
- `lambdas/raw_ingestion/`
  - `trade_event/` y `price_history/` (ingestores), `contracts/`, `lib/` comun.
- `orchestration/`
  - Definiciones de pipeline/orquestacion de la fase 1.
- `docs/`
  - Diagramas y notas operativas de ingesta.

### `reporting-infra-phase2-data-lake`

- `terraform/`
  - Buckets standardized/silver/artifacts, Glue, Athena y Lambdas de fase 2.
- `glue-data-lake/`
  - `jobs/` ETL por capa, `contracts/`, `sqls/`, `config/`.
- `lambdas/`
  - `lake_pipeline_stream_router/`, `glue_job_status_dynamo/`, `glue_schema_athena/`.
- `../reporting-infra-schema-registry/schemas/glue/`
  - DDL Glue/Athena centralizados (`raw/`, `standardized_s3/`, `silver_s3/`).

### `reporting-infra-phase3-redshift`

- `terraform/`
  - Redshift Serverless, Lambda SQL, Step Functions COPY/gold e IAM.
- `redshift/`
  - `jobs-sql/` (scripts por etapa), `contracts/`.
- `lambdas/redshift_sql/`
  - Ejecutor SQL via Data API + escritura de capas en Dynamo.
- `lambdas/redshift_sfn_stream_router/`
  - Router: DynamoDB Stream → `StartExecution` de Step Functions COPY/gold (misma idea que `lake_pipeline_stream_router` en fase 2).
- `../reporting-infra-schema-registry/schemas/redshift/`
  - DDL Redshift centralizados (`silver/`, `gold/`).

## 3) Secuencia funcional esperada

1. Ingesta (fase 1) termina lote RAW valido y **escribe** la capa `raw` en Dynamo (codigo de fase 1).
2. El stream detecta `raw` SUCCEEDED → **router lake** (fase 2) dispara Glue `validated_to_standardized`.
3. Glue finaliza y **registra** `lake_validated_to_standardized` en Dynamo (Glue + `glue_job_status_dynamo` / finish).
4. Stream → router lake → Glue `standardized_to_silver`.
5. Glue **registra** `lake_standardized_to_silver` en Dynamo.
6. Stream → **router Redshift** (fase 3) → SFN COPY.
7. SFN COPY ejecuta `redshift_sql` **por cada `.sql`** en orden; el estado en Dynamo lo escribe esta Lambda (`record_redshift_layer`).
8. Stream → router Redshift → SFN gold.
9. SFN gold ejecuta `redshift_sql` por cada `.sql`; capa terminal `gold` en Dynamo.

## 4) Como interactuan las Lambdas

Las Lambdas **no dependen de importarse entre si** entre repos. Se coordinan por servicios AWS:

- DynamoDB stream + routers por fase (avance entre repos),
- DynamoDB (estado/gate),
- Glue y Step Functions (ejecucion de la siguiente capa).

Esto permite despliegues separados por repo sin perder flujo conjunto.

### Nota importante sobre RAW

- RAW no se divide en dos buckets logicos distintos en V1.
- La escritura ocurre en **un único bucket RAW** y se segmenta por prefijos:
  - `validated/<tabla>/...` cuando cumple contrato,
  - `rejected/<tabla>/...` cuando falla contrato.

## 5) Reglas clave para que funcione bien

- Activar `enable_pipeline_dynamo = true` en fases 1, 2 y 3.
- Activar `enable_pipeline_ddb_stream_chain = true` en fases 1, 2 y 3 (tabla con stream en dynamo-platform).
- Mantener alineadas las listas `pipeline_copy_scripts_order` y `pipeline_gold_scripts_order` en fase 3 (SFN).
- Operar con esta arquitectura por capas y repos desacoplados.

## 6) Orden de despliegue recomendado

1. `reporting-infra-dynamo-platform`
2. `reporting-infra-phase1-landing-ingestion`
3. `reporting-infra-phase3-redshift`
4. `reporting-infra-phase2-data-lake`
5. `reporting-infra-schema-registry`

## 7) Que validar en AWS despues de desplegar

- Existen tabla `pipeline_runs` y permisos IAM de pipeline.
- La ingesta escribe en `validated/` y/o `rejected/`.
- Los eventos `ReportingPipelineLayerSucceeded` aparecen en EventBridge.
- Router dispara Glue/SFN segun `layer`.
- SFN COPY y SFN gold ejecutan un estado por `.sql`.
- Dynamo registra estados por capa (`raw`, `lake_*`, `redshift_silver`, `gold`).

## 8) Estado objetivo

Si todo esta correcto, cada corrida recorre:

`raw -> lake_validated_to_standardized -> lake_standardized_to_silver -> redshift_silver -> gold`

y queda trazabilidad completa en Dynamo + logs de Lambda/Glue/Step Functions.
