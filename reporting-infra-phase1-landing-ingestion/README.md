# Reporting — Fase 1: Landing e ingesta a RAW

| Campo | Detalle |
|-------|---------|
| **Componente** | Ingesta API → Amazon S3 (capa RAW) |
| **Repositorio** | `reporting-infra-phase1-landing-ingestion` |
| **Documentación gráfica** | [`docs/diagramas/arquitectura_ingesta.mmd`](docs/diagramas/arquitectura_ingesta.mmd) (Mermaid) |

---

## 1. Resumen ejecutivo

Este repositorio implementa la **primera fase** del pipeline de reporting: obtención de datos desde APIs externas, **validación contractual** y persistencia en un **bucket Amazon S3** dedicado a la capa RAW. La solución se despliega mediante **HashiCorp Terraform** e incluye una **función AWS Lambda**, una **Step Functions** para orquestación programada y **Amazon EventBridge** para ejecución recurrente.

No es obligatorio desplegar las fases posteriores (data lake, Redshift, orquestación global) para operar únicamente la ingesta hacia RAW.

---

## 2. Objetivo

- Centralizar la extracción de datos de negocio en formato crudo (**JSON** y **CSV**).
- Garantizar **trazabilidad y calidad mínima** mediante contratos versionados almacenados en el repositorio.
- Escribir los artefactos únicamente bajo prefijos **`validated/`** o **`rejected/`**, evitando rutas planas heredadas (`trade_event/`, `price_history/` en la raíz del bucket).

---

## 3. Alcance

| Incluido | Excluido (fases posteriores) |
|----------|------------------------------|
| Bucket S3 RAW, Lambda de ingesta, SFN 04, regla EventBridge (cron) | Glue, Athena, capas standardized/silver |
| Contratos y validación en Lambda; opcional escritura en **DynamoDB** (`enable_pipeline_dynamo`, repo `reporting-infra-dynamo-platform`) | Step Functions 01–03, Redshift (salvo integración manual) |
| Integración con Secrets Manager y configuración por ambiente | Enriquecimiento analítico post-RAW |

---

## 4. Arquitectura de referencia

El flujo de ingesta (Lambda → `validated/` / `rejected/`), su consumo por Glue en la fase 2 y el encadenamiento por capas (EventBridge + DynamoDB) hacia Redshift se representan en un único diagrama **Mermaid**:

- [`docs/diagramas/arquitectura_ingesta.mmd`](docs/diagramas/arquitectura_ingesta.mmd)

Cómo visualizarlo: [`docs/diagramas/README.md`](docs/diagramas/README.md).

---

## 5. Componentes desplegados

| Recurso | Función |
|---------|---------|
| **Amazon S3** | Almacenamiento de objetos en capa RAW con prefijos `validated/` y `rejected/`. |
| **AWS Lambda** | Ejecución del proceso de ingesta (`lambdas/raw_ingestion/`). |
| **AWS Step Functions** | Orquestación **SFN 04**: ramas paralelas para `trade_event` y `price_history`. |
| **Amazon EventBridge** | Regla programada (cron) que inicia la SFN 04. |
| **AWS Secrets Manager** | Almacenamiento de credenciales para APIs (configurable vía Terraform). |
| **Amazon CloudWatch Logs** | Registro de ejecución de la Lambda (retención parametrizable). |

---

## 6. Contratos y validación de datos

| Origen | Formato | Comportamiento |
|--------|---------|------------------|
| **trade_event** | JSON | Validación frente a `contracts/trade_event.contract.json`. Rechazo: prefijo `rejected/`, trazabilidad en log con `[INGEST_REJECTED]`. |
| **price_history** | CSV | Validación de cabecera y tipos según `contracts/price_history.contract.json`. La primera fila inválida implica rechazo del lote completo (criterio estricto). |

Los esquemas en Glue/Athena de la fase 2 apuntan a **`s3://<bucket_raw>/validated/<tabla>/`**. El job Glue *validated → standardized* consume exclusivamente ese prefijo.

---

## 7. Prerrequisitos operativos

1. **Credenciales**: Secreto en Secrets Manager coherente con `api_secret_name` en la configuración por ambiente. Terraform puede crear el contenedor del secreto; el valor debe cargarse de forma segura (consola, CI/CD o `terraform apply -var=...` según política de la organización).
2. **Endpoints**: URLs reales en `lambdas/raw_ingestion/*/config/<ambiente>.json`. Cualquier modificación requiere **nuevo empaquetado** de la Lambda (`terraform apply`).
3. **Coherencia de ambiente**: El valor `environment` en `terraform.tfvars` debe coincidir con el archivo de configuración (`dev` → `config/dev.json`, etc.).

---

## 8. Despliegue (Terraform)

Entornos preparados: `terraform/envs/dev`, `envs/test`, `envs/prod` (estados remotos independientes). Detalle: [`terraform/envs/README.md`](terraform/envs/README.md).

```bash
cd terraform/envs/dev   # o test / prod
cp terraform.tfvars.example terraform.tfvars   # ajustar parámetros
terraform init
terraform plan
terraform apply
```

Parámetro opcional: `phase1_repository_root` si la ruta del código respecto a Terraform no es la predeterminada.

---

## 9. Operación y monitoreo

- **Disparo**: Regla programada, ejecución de la **SFN 04**, o invocación directa de la Lambda con payload  
  `{"job":"trade_event/ingest.py"}` o `{"job":"price_history/ingest.py"}`.
- **Logs**: Grupo `/aws/lambda/<prefijo>-run-raw-api-ingestion` (retención: `lambda_log_retention_days`, por defecto 14 días). Si el grupo existía previamente sin gestión por Terraform, puede ser necesario **import** del recurso según procedimiento interno.

---

## 10. Integración con el ecosistema Reporting

Orden de despliegue recomendado en el resto del workspace: **`reporting-infra-dynamo-platform`** (estado de pipeline) → **fase 3** (Redshift) → **fase 2** (data lake) → **schema registry**. Arquitectura: [`../docs/ARQUITECTURA.md`](../docs/ARQUITECTURA.md).

---

## 11. Estructura del repositorio

```
reporting-infra-phase1-landing-ingestion/
├── docs/
│   └── diagramas/          # arquitectura_ingesta.mmd (Mermaid) + README
├── lambdas/raw_ingestion/  # Handler, jobs, biblioteca, contratos, configs
├── orchestration/pipelines/ # Definición SFN 04
└── terraform/envs/         # Infraestructura por ambiente
```

---

## 12. Referencias

| Documento | Ubicación |
|-----------|-----------|
| Despliegue multi-fase | `docs/TECNICO_DEPLOY.md` (repositorio raíz del workspace) |
| Diagrama de arquitectura de ingesta | `docs/diagramas/arquitectura_ingesta.mmd` |
| Entornos Terraform | `terraform/envs/README.md` |

**GitLab:** [ca-group4/reporting-infra-phase1-landing-ingestion](https://gitlab.com/ca-group4/reporting-infra-phase1-landing-ingestion)
