# reporting-infra-dynamo-platform

Repositorio **plataforma**: **Amazon DynamoDB** para estado de corridas del pipeline (por `business_date`), bucket **S3** de archivo histórico y **Lambda** programada (p. ej. lunes 00:00 UTC) que exporta ítems viejos y los elimina de la tabla.

**Desplegar este repo antes** que las fases de ingesta / data lake / Redshift que escriben o leen ese estado.

## Contenido

| Recurso | Descripción |
|---------|-------------|
| `aws_dynamodb_table.pipeline_runs` | PK/SK + GSI `gsi_env_business_date` para consultas por entorno y fecha. |
| S3 `*-dynamo-archive-*` | Objetos JSON por ítem archivado. |
| Lambda `*-dynamo-archive-job` | Query GSI + `PutObject` + `DeleteItem`. |
| EventBridge | Regla cron semanal (configurable). |
| IAM | Política `*-pipeline-runs-access` para adjuntar a Lambdas de fases 1–3. |
| SSM | `/reporting/<env>/pipeline/dynamodb/*` (nombre tabla, ARN, `env_key`, bucket archivo). |

## Esquema de ítems

Ver [docs/DYNAMODB_SCHEMA.md](docs/DYNAMODB_SCHEMA.md).

## Terraform

```bash
cd terraform/envs/dev
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

## Orden de deploy global

1. Este repo (tabla + archivo).
2. Fase 1 / 2 / 3 (con `enable_pipeline_dynamo` o equivalente y remote state apuntando aquí).

Docs del workspace: arquitectura [`../docs/ARQUITECTURA.md`](../docs/ARQUITECTURA.md) y guía técnica [`../docs/TECNICO_DEPLOY.md`](../docs/TECNICO_DEPLOY.md).
