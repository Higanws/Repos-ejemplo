# reporting-infra-schema-registry

Repositorio central para consolidar y ejecutar schemas de:

- Glue Data Catalog / Athena (capas `standardized_s3`, `silver_s3`)
- Redshift (capas `silver`, `gold`)

## Objetivo

Tener una única fuente de verdad para DDL y un comando **on-demand** para crear/actualizar tablas.

## Estructura

- `schemas/glue/**`: DDL de Athena/Glue (external tables).
- `schemas/redshift/**`: DDL de Redshift.
- `schemas/manifest.json`: orden de ejecución por motor.
- `tools/run_schemas.py`: ejecutor on-demand.

## Uso rápido

## Opción A: Script on-demand (CLI)

### 1) Crear tablas Glue/Athena

```bash
python tools/run_schemas.py ^
  --target glue ^
  --aws-region sa-east-1 ^
  --standardized-bucket <standardized-bucket> ^
  --silver-bucket <silver-bucket> ^
  --athena-workgroup <athena-workgroup> ^
  --athena-output-s3 s3://<bucket-athena-results>/queries/
```

### 2) Crear tablas Redshift

```bash
python tools/run_schemas.py ^
  --target redshift ^
  --aws-region sa-east-1 ^
  --redshift-workgroup <workgroup> ^
  --redshift-database <database> ^
  --redshift-secret-arn <secret-arn>
```

### 3) Ejecutar todo (Glue + Redshift)

```bash
python tools/run_schemas.py ^
  --target all ^
  --aws-region sa-east-1 ^
  --standardized-bucket <standardized-bucket> ^
  --silver-bucket <silver-bucket> ^
  --athena-workgroup <athena-workgroup> ^
  --athena-output-s3 s3://<bucket-athena-results>/queries/ ^
  --redshift-workgroup <workgroup> ^
  --redshift-database <database> ^
  --redshift-secret-arn <secret-arn>
```

## Flags útiles

- `--force-ddl`: ejecuta aunque detecte tabla existente.
- `--dry-run`: muestra orden/scripts sin ejecutar.

## Opción B: Lambda (manual en consola + auto en deploy)

Se agregó Terraform en `terraform/envs/dev` que despliega la Lambda:

- nombre: `${project}-${environment}-schema-registry-apply`
- handler: `lambdas/schema_registry/main.handler`
- usa remote state de fase 2/3 para tomar buckets/workgroup/database/secret

### Deploy

```bash
cd terraform/envs/dev
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

Si `invoke_on_apply = true`, en cada `terraform apply` se invoca la Lambda y aplica DDL (`invoke_target = "all"` por defecto).

### Invocación manual desde consola AWS

Evento de ejemplo:

```json
{
  "target": "all",
  "force_ddl": false,
  "dry_run": false
}
```

También soporta `target: "glue"` o `target: "redshift"`.

## Nota de migración

RAW no se modela aquí como tablas Glue: es un bucket/prefijo crudo validado por contrato en fase 1.
