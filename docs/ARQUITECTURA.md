# Arquitectura unificada (V1)

## 1) Vista general

La plataforma está dividida en 5 repos Terraform:

- `reporting-infra-dynamo-platform`: estado de pipeline (`pipeline_runs`), stream, archivado e IAM compartido.
- `reporting-infra-phase1-landing-ingestion`: ingesta API a RAW (`validated/` y `rejected/`); **escribe** la capa `raw` en Dynamo desde su propia lógica (`pipeline_dynamo`).
- `reporting-infra-phase2-data-lake`: Glue (validated→standardized→silver), Athena; **router de fase 2** `lake_pipeline_stream_router` lee el stream y arranca Glue; **escritura** de capas Glue en Dynamo vía `glue_job_status_dynamo` + `pipeline_layer_finish` en jobs.
- `reporting-infra-phase3-redshift`: Redshift + Step Functions + `redshift_sql`; **router** `redshift_sfn_stream_router` lee el stream y arranca SFN; **escritura** de capas en Dynamo desde la Lambda **`pipeline_runs_dynamo`** (invocada por `redshift_sql`), mismo patrón que `glue_job_status_dynamo` en fase 2.
- `reporting-infra-schema-registry`: DDL centralizados (Glue/Athena + Redshift) y Lambda de aplicación on-demand.

## 2) Flujo por capas (DynamoDB como contrato entre fases)

1. Fase 1 valida contratos, escribe en S3 y marca la capa **`raw`** en `pipeline_runs` (repo fase 1).
2. El **stream** de DynamoDB dispara el **router lake** (fase 2) → Glue `validated_to_standardized`.
3. Al terminar, se registra **`lake_validated_to_standardized`** en Dynamo (Glue + `glue_job_status_dynamo` / finish).
4. El stream dispara de nuevo el router lake → Glue `standardized_to_silver`.
5. Se registra **`lake_standardized_to_silver`** en Dynamo.
6. El stream dispara el **router Redshift** (fase 3) → Step Functions **COPY** (Lambda `redshift_sql`).
7. Tras COPY, el estado **`redshift_silver`** queda en Dynamo (esta Lambda).
8. El stream dispara el router Redshift → SFN **gold**.
9. Tras gold, **`gold`** en Dynamo (fin de cadena).

No hay router unificado ni encadenamiento por `PutEvents` al bus: cada repo **posee** las funciones que actualizan Dynamo para su tramo; los routers solo **leen** transiciones en el stream y lanzan Glue o SFN.

Activar la cadena: `enable_pipeline_ddb_stream_chain = true` en fases 1–3 (y `enable_pipeline_dynamo`).

## 3) Coordinación entre componentes

- **DynamoDB** `pipeline_runs`: fuente de verdad y **Stream** para routers por fase.
- **Glue** y **Step Functions**: ejecución técnica disparada por los routers.

## 4) Estado y trazabilidad

- Tabla `pipeline_runs` en DynamoDB.
- Claves por corrida:
  - `pk = PIPE#{project}#{env}#BDATE#{business_date}`
  - `sk = RUN#{batch_id}`
- Registro por capa en `layers` + traza en `execution_log`.

## 5) DDL centralizado

- Glue/Athena: `reporting-infra-schema-registry/schemas/glue/`
- Redshift: `reporting-infra-schema-registry/schemas/redshift/`

Fase 2 y fase 3 publican estos DDL al bucket de artifacts durante `terraform apply`.

## 6) Orden de despliegue recomendado

1. `reporting-infra-dynamo-platform`
2. `reporting-infra-phase1-landing-ingestion`
3. `reporting-infra-phase3-redshift`
4. `reporting-infra-phase2-data-lake`
5. `reporting-infra-schema-registry`

## 7) Observabilidad

- Lambda logs: `/aws/lambda/<nombre>`
- Glue logs: `/aws-glue/jobs/<job-name>`
- Step Functions: historial por state machine
- Redshift Data API: historial de ejecución SQL

## 8) Diagrama

Ver `docs/arquitectura_general.mmd`.
