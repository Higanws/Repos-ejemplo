# Terraform por ambiente (dev / test / prod)

Cada carpeta es un **directorio de trabajo independiente** de Terraform:

| Carpeta | State en S3 (`key`) | Recursos típicos en AWS |
|---------|---------------------|-------------------------|
| `dev/`  | `.../dev/terraform.tfstate`  | `reporting-dev-*` |
| `test/` | `.../test/terraform.tfstate` | `reporting-test-*` |
| `prod/` | `.../prod/terraform.tfstate` | `reporting-prod-*` |

**El repo contiene las tres carpetas.** No se “sube solo dev”: Git guarda todo el código. Lo que cambia es **desde dónde corrés** Terraform:

```powershell
cd terraform/envs/dev    # solo afecta recursos de dev (ese state)
terraform apply

cd ../test
terraform init         # primera vez en test
terraform apply        # crea reporting-test-* en paralelo a dev
```

Cada ambiente tiene su propio **bucket RAW**, **Lambda**, **SFN 04**, etc. (nombres con `reporting-<env>-`).

**Config de ingesta:** `lambdas/raw_ingestion/*/config/dev.json`, `test.json`, `prod.json` deben alinearse con `environment` en el `terraform.tfvars` de esa carpeta.

Copiá `terraform.tfvars.example` → `terraform.tfvars` en cada ambiente (no subir secretos a Git).
