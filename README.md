# Reporting — plataforma de datos (por fases)

Cuatro repos **independientes** de Terraform para la plataforma (ingesta → lake → Redshift + schema-registry), más **`reporting-infra-dynamo-platform`** para estado de pipeline en DynamoDB. El orden de despliegue recomendado es **dynamo-platform → 1 → 3 → 2 → schema-registry**. Podés aplicar **solo la fase 1** para tener ingesta y RAW; el resto es opcional.

| Orden | Carpeta | Rol breve |
|------|---------|-----------|
| 0 | `reporting-infra-dynamo-platform` | Tabla `pipeline_runs`, archivo S3, IAM pipeline, SSM |
| 1 | `reporting-infra-phase1-landing-ingestion` | S3 RAW, Lambda ingesta, SFN 04, cron |
| 2 | `reporting-infra-phase3-redshift` | Redshift Serverless, Lambda SQL, jobs SQL en S3 |
| 3 | `reporting-infra-phase2-data-lake` | Lake S3, Glue, Athena, RAW→std→silver, router |
| 4 | `reporting-infra-schema-registry` | DDL centralizados + Lambda on-demand para crear tablas Glue/Redshift |

**Nota:** el flujo operativo vigente es **V1 por capas** con EventBridge, DynamoDB, Glue y Step Functions.

| Documento | Contenido |
|-----------|-----------|
| [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) | Arquitectura, flujo por capas y componentes |
| [`docs/TECNICO_DEPLOY.md`](docs/TECNICO_DEPLOY.md) | Guía técnica de despliegue, operación y ejecución manual |

Cada carpeta `reporting-infra-*` tiene su propio **README** con estructura de archivos y notas operativas.
