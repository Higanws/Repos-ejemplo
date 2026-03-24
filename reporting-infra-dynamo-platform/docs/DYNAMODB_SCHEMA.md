# Esquema DynamoDB — `pipeline_runs`

Tabla: `${project}-${environment}-pipeline-runs` (ej. `reporting-dev-pipeline-runs`).

## Claves


| Atributo | Tipo           | Uso                                       |
| -------- | -------------- | ----------------------------------------- |
| `pk`     | String (HASH)  | `PIPE#<project>#<env>#BDATE#<YYYY-MM-DD>` |
| `sk`     | String (RANGE) | `RUN#<batch_id o uuid>`                   |


## GSI `gsi_env_business_date`


| Atributo        | Tipo           | Uso                    |
| --------------- | -------------- | ---------------------- |
| `env_key`       | String (HASH)  | `PIPE#<project>#<env>` |
| `business_date` | String (RANGE) | `YYYY-MM-DD`           |


**Proyección:** `ALL`.

## Cadena de capas (orden lineal)

Cada capa **valida** que la anterior esté `SUCCEEDED` antes de ejecutar (salvo la primera). Tras éxito, la capa escribe su clave en `layers` y (según automatización) puede disparar la siguiente.


| Orden | Clave en `layers`                | Quién escribe                                             | Valida antes de ejecutar             |
| ----- | -------------------------------- | --------------------------------------------------------- | ------------------------------------ |
| 1     | `raw`                            | Fase 1 ingesta                                            | — (no hay anterior)                  |
| 2     | `lake_validated_to_standardized` | Lambda `glue_job_status_dynamo` (job Glue 1)              | `raw` (gate en script Glue + Dynamo) |
| 3     | `lake_standardized_to_silver`    | Misma Lambda (job Glue 2)                                 | `lake_validated_to_standardized`     |
| 4     | `redshift_silver`                | Fase 3 `redshift_sql` (scripts bajo `copy_s3_to_silver/`) | `lake_standardized_to_silver`        |
| 5     | `gold`                           | Fase 3 `redshift_sql` (scripts bajo `silver_to_gold/`)    | `redshift_silver`                    |


**Última capa:** `gold` no tiene “siguiente” en Dynamo (salvo orquestación externa).

**Compatibilidad:** ítems antiguos pueden tener solo `layers.redshift` (unificado); la validación de COPY acepta `redshift` o `redshift_silver` como capa previa satisfactoria para `gold`.

Cada valor en `layers` es un mapa tipo `{ "status": "SUCCEEDED"|"FAILED", "updated_at": "ISO8601", ... }`.

## `execution_log`

Lista de entradas cortas `{ "t", "layer", "action", ... }` (append con `list_append`).

## `tables` (fase 1)

Detalle por tabla en RAW (`trade_event`, `price_history`, …).

## Contratos de entrada

No se guarda el JSON completo; sí **versiones** opcionales (`contract_set_version_phase1`, etc.).

## Idempotencia

- Misma `pk` + `sk` por corrida lógica.
- `UpdateItem` con condiciones si hace falta evitar doble OK.

## Automatización entre capas

- **DynamoDB Streams + routers por repo:** `enable_pipeline_ddb_stream_chain` en fases 1–3 y stream en `pipeline_runs`. Cada fase **escribe** su capa en Dynamo con su propio código (ingesta, Glue status/finish, `redshift_sql`). **Fase 2:** `lake_pipeline_stream_router` reacciona a `raw` y `lake_validated_to_standardized` y arranca Glue. **Fase 3:** `redshift_sfn_stream_router` reacciona a `lake_standardized_to_silver` y `redshift_silver` y arranca Step Functions. No se usa `PutEvents` para encadenar.
- **Glue 1 → Glue 2 directo (sin stream):** con `glue_auto_chain_to_next_job` y sin `enable_pipeline_ddb_stream_chain`, la Lambda `glue_job_status_dynamo` puede llamar `glue:StartJobRun` al segundo Glue.

Ver `[../../docs/ARQUITECTURA.md](../../docs/ARQUITECTURA.md)`.

