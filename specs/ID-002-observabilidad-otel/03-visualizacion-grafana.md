# ID-002 — Fase 3: Visualización y correlación en ECS

> Esta fase se implementa después de leer este documento, [`00-especificacion.md`](00-especificacion.md) y [`00-plan-general.md`](00-plan-general.md). El cierre sigue el Gate 3 de [`GUIA-AGENTE.md`](../GUIA-AGENTE.md).

## Identificación

| Campo | Detalle |
|---|---|
| Plan | ID-002 — Observabilidad OpenTelemetry local, ECS y visualización. |
| Fase | 3 — Visualización y correlación en ECS |
| Estado | Pendiente |
| Requisitos | RF-018–RF-022, RNF-008–RNF-009; validación extremo a extremo de RF-002, RF-011–RF-013 y RF-019. |
| Sistemas y repositorios | Aplicación, `infra/otel-ecs-lab` y módulos Terraform compartidos en `infra/tf_modules`. |
| Dependencias previas | Fases 1 y 2; despliegue ECS activo; imágenes publicadas; CIDR de prueba disponible; permisos Terraform/ECR/ECS/CloudWatch. |
| Habilita a | Ninguna fase posterior definida. |

## Objetivo

Consultar en Grafana un dashboard de seis paneles y localizar desde Grafana Explore la traza Jaeger asociada a un `trace_id` encontrado en CloudWatch Logs. El laboratorio conserva una sola instancia efímera de Jaeger en ECS y agrega Grafana como contenedor efímero de la misma tarea.

## Contexto de la fase

La fase 2 despliega Jaeger, Prometheus, el OTel Collector y CloudWatch Logs en ECS. Los backends tienen endpoints funcionales, pero todavía no hay una vista común de SLIs, CPU, errores del Collector y correlación entre registros y trazas. El despliegue reciente confirmó una tarea ECS estable; falta validar los datos funcionales en las interfaces.

## Alcance técnico

### Cambios previstos

| Ubicación | Cambio | Requisito asociado |
|---|---|---|
| `docker/grafana/Dockerfile` | Construir una imagen Grafana con versión base fijada y provisionar datasources y dashboard desde archivos versionados. | RF-018, RF-020, RF-021, RNF-009 |
| `docker/grafana/provisioning/` | Configurar datasources Prometheus, Jaeger y CloudWatch; cargar el dashboard al arrancar. | RF-018–RF-021 |
| `docker/grafana/dashboards/` | Definir el dashboard de seis paneles descrito abajo. | RF-020 |
| `scripts/push-ecs-images.py` y ECR | Incluir la imagen Grafana en la publicación versionada de imágenes. | RF-018, RNF-009 |
| `infra/tf_modules/ecs` | Agregar Grafana a la task definition, publicar el puerto 3000 y ajustar CPU/memoria para el laboratorio. | RF-018, RF-020, RF-022 |
| `infra/tf_modules/network` | Permitir Grafana desde el CIDR configurado, sin ampliar otros puertos ni permitir `0.0.0.0/0`. | RF-022 |
| `infra/tf_modules/foundation` | Guardar la contraseña inicial de Grafana en Secrets Manager y limitar las acciones de consulta CloudWatch al alcance de los grupos requeridos. | RNF-008 |
| README y documentos de validación | Documentar el acceso a Grafana, los smoke tests, la limpieza y el formato de evidencias. | RF-018–RF-022 |

### No incluido en esta fase

- Desplegar Jaeger en GCP, AWS X-Ray, Tempo, Grafana Cloud o Amazon Managed Grafana.
- Persistir dashboards, trazas o datos de negocio después de eliminar la tarea ECS.
- Crear alertas productivas, objetivos de disponibilidad, Container Insights o métricas de negocio.
- Exponer Prometheus, Jaeger, PostgreSQL o el endpoint interno del Collector fuera de las reglas ya existentes.

## Diseño

Grafana comparte la red `awsvpc` de la tarea y consulta Prometheus y Jaeger mediante `localhost`; consulta métricas ECS y logs a través de la API CloudWatch en `us-east-1` usando las credenciales del task role. Se provisionan los datasources y el dashboard durante el build de la imagen, por lo que reemplazar la tarea no requiere pasos manuales. La clave administrativa se obtiene desde Secrets Manager y no se incluye en la imagen ni en el dashboard.

El grupo de seguridad publica el puerto 3000 solo para `allowed_cidr`. Jaeger permanece en el puerto 16686 y Prometheus en 9090, bajo las reglas existentes. Todos los contenedores de una tarea Fargate comparten el task role: las acciones de lectura para Grafana deben quedar limitadas a los grupos de CloudWatch de la aplicación y del Collector, además de las métricas ECS necesarias. No se agregan permisos de escritura de datos a Grafana.

El tamaño actual de la tarea es 1 vCPU y 2 GiB. La configuración de fase usa 1 vCPU y 3 GiB, combinación válida en Fargate Linux, para incluir Grafana y conservar margen en las pruebas. La evidencia de ECS debe confirmar que todos los contenedores permanecen `RUNNING`, sin parada por falta de memoria.

### Dashboard de seis paneles

| # | Panel | Fuente | Definición de la consulta | Resultado esperado |
|---|---|---|---|---|
| 1 | Éxito HTTP — catálogo | Prometheus | Proporción de respuestas 2xx/3xx sobre todas las solicitudes del servicio en ventana de 5 minutos. | Serie porcentual no vacía tras enviar tráfico. |
| 2 | Latencia HTTP p95 — catálogo | Prometheus | Percentil 95 del histograma de duración HTTP del servicio, en segundos o milisegundos rotulados. | Serie no vacía tras enviar tráfico. |
| 3 | Éxito HTTP — pedidos | Prometheus | Proporción de respuestas 2xx/3xx sobre todas las solicitudes del servicio en ventana de 5 minutos. | Serie porcentual no vacía tras enviar tráfico. |
| 4 | Latencia HTTP p95 — pedidos | Prometheus | Percentil 95 del histograma de duración HTTP del servicio, en segundos o milisegundos rotulados. | Serie no vacía tras enviar tráfico. |
| 5 | CPU del servicio ECS | CloudWatch Metrics | `AWS/ECS/CPUUtilization`, dimensiones `ClusterName` y `ServiceName`, estadística Average, región `us-east-1`. | Puntos de datos dentro de la ventana de tiempo. |
| 6 | Errores OTel Collector | CloudWatch Logs Insights | Conteo por minuto de eventos con nivel `error`/`ERROR` o texto de fallo del stream del contenedor `otel-collector`. | Serie de conteos, incluido cero cuando no haya errores; el error `pipeline_up` observado durante el despliegue sirve para comprobar la consulta inicial. |

Los nombres y etiquetas Prometheus se fijan después de consultar `/metrics` del Collector y Prometheus. La consulta exacta debe usar los nombres emitidos por la versión del SDK desplegada y `service.name`; los paneles no se aceptan con consultas vacías o métricas ficticias.

Como punto de partida después de verificar que la serie y etiquetas existen, la tasa de éxito usa la forma `100 * solicitudes con status 2xx/3xx / todas las solicitudes` en una ventana de 5 minutos. La latencia p95 usa `histogram_quantile(0.95, sum by (le) (rate(<histograma>_bucket{service_name="catalog"}[5m])))`; se replica para `orders`. Si el exporter agrega un prefijo como `pipeline_` o transforma una etiqueta, se usa el nombre observado en Prometheus. El panel de errores parte de esta consulta Logs Insights y la ajusta al formato real del stream:

```text
fields @timestamp, @message, @logStream
| filter @logStream like /otel-collector/
| filter @message like /error|ERROR|failed/
| stats count(*) as errors by bin(1m)
```

### Comportamiento esperado por caso

| Caso | Condición | Resultado esperado |
|---|---|---|
| C-014 | Se envía tráfico exitoso y 4xx a catálogo y pedidos. | Las tasas de éxito se ajustan a las respuestas observadas y las latencias se muestran. |
| C-015 | Se crea un pedido válido y se consulta su log JSON en Grafana Explore. | El `trace_id` permite abrir la misma traza en la fuente Jaeger de Grafana y ver `orders`, `catalog` y operaciones SQL. |
| C-016 | La tarea ECS está `RUNNING`. | El panel de CPU recibe datos para el cluster y el servicio correctos. |
| C-017 | Se filtran los eventos del contenedor OTel Collector. | El panel y Explore encuentran los eventos de error del Collector sin mezclar logs de otras aplicaciones. |
| C-018 | Se reinicia o reemplaza la tarea. | Grafana vuelve con fuentes y dashboard provisionados; las trazas y los datos temporales previos pueden perderse según el diseño efímero. |
| C-019 | Se intenta abrir Grafana desde un origen fuera de `allowed_cidr`. | No se obtiene acceso al puerto 3000. |

## Tareas

Las tareas marcadas con `[P]` pueden ejecutarse en paralelo.

| Estado | # | Tarea | Criterio de aceptación |
|---|---|---|---|
| [ ] | 1 | Confirmar los nombres reales de métricas y etiquetas disponibles en Prometheus para ambas APIs. | Se conservan muestras de `/metrics` y consultas PromQL que retornan datos; se anotan nombres/labels en el dashboard. |
| [ ] | 2 | `[P]` Crear la imagen Grafana con versión fijada y archivos de provisioning. | `docker build` finaliza; config y dashboard pasan sus validaciones JSON/YAML; Grafana carga las tres fuentes. |
| [ ] | 3 | `[P]` Agregar el repositorio ECR y ampliar el script para construir/publicar Grafana con tag inmutable. | El tag Grafana aparece en ECR y coincide con el tag de la task definition. |
| [ ] | 4 | `[P]` Definir el dashboard y las consultas del panel CloudWatch Logs Insights. | Existen exactamente seis paneles; las consultas no contienen credenciales ni recursos de otra cuenta. |
| [ ] | 5 | Extender Terraform con Grafana, permisos mínimos, secreto de administración, puerto 3000 limitado y tamaño de tarea de 1 vCPU/3 GiB. | `terraform fmt`, `validate` y `plan` pasan; el plan muestra solo recursos/cambios previstos. |
| [ ] | 6 | Construir, publicar y aplicar el nuevo tag inmutable; esperar estabilización de ECS. | Rollout `COMPLETED`, una tarea `RUNNING`, contenedores esenciales saludables/en ejecución y migraciones con código 0. |
| [ ] | 7 | Ejecutar el recorrido funcional, consultar el dashboard y pivotar entre log y traza. | Se obtienen las evidencias descritas en la sección siguiente. |
| [ ] | 8 | Destruir el laboratorio después de exportar evidencia y verificar limpieza. | No queda servicio/tarea ECS del laboratorio ni recursos nuevos de Grafana; evidencia exportada sin secretos. |

## Validación y captura de evidencias

Las validaciones automatizadas confirman sintaxis e infraestructura. Las pruebas funcionales se ejecutan contra el despliegue AWS real y permanecen `Pendientes de confirmación` hasta registrar sus salidas o capturas. Crear el directorio antes de comenzar:

```sh
mkdir -p specs/ID-002-observabilidad-otel/evidencias/fase-03
```

Guardar allí los artefactos; redactar o excluir secretos, contraseñas, tokens y salidas de Secrets Manager.

### 1. Validación estática antes del despliegue

Desde el repositorio de aplicación:

```sh
docker compose config --quiet
python3 -m json.tool docker/grafana/dashboards/otel-lab.json >/dev/null
```

Desde la raíz del repositorio:

```sh
terraform -chdir=infra/otel-ecs-lab fmt -check -recursive
terraform -chdir=infra/otel-ecs-lab init
terraform -chdir=infra/otel-ecs-lab validate
```

Para incluir también los módulos compartidos, ejecutar desde la raíz `terraform fmt -check -recursive infra/otel-ecs-lab && terraform fmt -check -recursive infra/tf_modules`.

**Evidencia:** `01-validacion-estatica.txt` con los comandos y códigos de salida.

### 2. Confirmación del despliegue

Primero crear el repositorio ECR nuevo sin reemplazar los repositorios existentes y publicar Grafana con un tag nuevo (ECR usa tags inmutables). Luego generar y revisar el plan completo:

```sh
terraform apply -target='module.ecr.aws_ecr_repository.images["grafana"]'
terraform output -json ecr_urls > /tmp/pipeline-otel-ecr-urls.json
python3 /home/ajfuq/projects/pipeline-otel-end-to-end/scripts/push-ecs-images.py us-east-1 /tmp/pipeline-otel-ecr-urls.json phase3-test-1
# Configurar image_tag = "phase3-test-1" en terraform.tfvars.
terraform plan -out=/tmp/phase3.tfplan
terraform show -no-color /tmp/phase3.tfplan
terraform apply /tmp/phase3.tfplan
aws ecs wait services-stable --region us-east-1 --cluster pipeline-otel-test --services pipeline-otel-test
aws ecs describe-services --region us-east-1 --cluster pipeline-otel-test --services pipeline-otel-test \
  --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount,taskDefinition:taskDefinition,deployments:deployments[].{status:status,rollout:rolloutState}}' \
  --output json
```

Revisar que el plan limite el puerto 3000 al CIDR autorizado, use el repositorio/tag publicados, añada permisos de lectura acotados y ajuste la tarea a 1 vCPU/3 GiB. No guardar el archivo binario del plan ni estado Terraform como evidencia compartida.

Registrar en `02-plan-sanitizado.txt` el resumen revisado de recursos que Terraform crea, modifica o destruye, omitiendo cualquier valor sensible.

Recuperar el task ID y confirmar los contenedores:

```sh
aws ecs list-tasks --region us-east-1 --cluster pipeline-otel-test --service-name pipeline-otel-test --desired-status RUNNING
aws ecs describe-tasks --region us-east-1 --cluster pipeline-otel-test --tasks TASK_ARN \
  --query 'tasks[0].{lastStatus:lastStatus,containers:containers[].{name:name,lastStatus:lastStatus,healthStatus:healthStatus,exitCode:exitCode,reason:reason}}' \
  --output json
```

**Evidencia:** `03-ecs-estable.json`, con cuenta/ARN/IP redactados si se comparte fuera del equipo. Debe mostrar rollout `COMPLETED`, `running=1`, `pending=0`, Grafana/Collector/Jaeger/Prometheus/APIs en ejecución, PostgreSQL saludable y ambas migraciones con `exitCode=0`.

### 3. Prueba de APIs, SLIs y dashboard

Obtener el task ARN con `aws ecs list-tasks`. Obtener de su attachment la ENI y luego la IP pública; configurar temporalmente `TASK_ARN`, `ENI_ID` y `TASK_IP` en la terminal:

```sh
TASK_ARN='arn:aws:ecs:us-east-1:CUENTA:task/pipeline-otel-test/TASK_ID'
ENI_ID=$(aws ecs describe-tasks --region us-east-1 --cluster pipeline-otel-test --tasks "$TASK_ARN" \
  --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value | [0]" --output text)
TASK_IP=$(aws ec2 describe-network-interfaces --region us-east-1 --network-interface-ids "$ENI_ID" \
  --query 'NetworkInterfaces[0].Association.PublicIp' --output text)
```

Crear tráfico representativo, conservando los códigos HTTP y cuerpos sin credenciales:

```sh
curl -i -X POST "http://${TASK_IP}:8001/products" \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: 30000000-0000-4000-8000-000000000001' \
  -d '{"name":"Evidencia fase 3","price":"12.50"}'

# Sustituir PRODUCT_ID por el id devuelto arriba.
curl -i -X POST "http://${TASK_IP}:8002/orders" \
  -H 'Content-Type: application/json' \
  -H 'X-Request-ID: 30000000-0000-4000-8000-000000000002' \
  -d '{"product_id":"PRODUCT_ID","quantity":2}'

# Generar respuestas 4xx controladas para que la tasa de éxito tenga ambos casos.
curl -i -X POST "http://${TASK_IP}:8001/products" -H 'Content-Type: application/json' -d '{}'
curl -i -X POST "http://${TASK_IP}:8002/orders" -H 'Content-Type: application/json' -d '{}'
```

Esperar dos scrapes de Prometheus y al menos dos puntos de CloudWatch; abrir `http://TASK_IP:3000` y fijar un rango temporal que cubra las solicitudes. Revisar los cuatro paneles HTTP, CPU y errores. Comparar las tasas con los códigos anotados por `curl`; p95 debe tener datos. Si un panel está vacío, revisar `/metrics`, Prometheus `/targets` y el estado de consultas antes de capturar evidencia.

**Evidencias:** `04-dashboard.png` que muestre los seis paneles y rango temporal; `05-prometheus-queries.txt` con consultas sin secretos y resultados no vacíos; `06-respuestas-http.txt` con los cuatro códigos de estado y el ID de producto/pedido parcialmente redactado.

### 4. Correlación log → traza

En Grafana Explore, seleccionar CloudWatch Logs, grupo `/pipeline-otel/ecs-test` y consultar los logs OTel de la solicitud de pedido por `request_id`. Identificar el campo `trace_id`. Si se inspecciona desde CloudWatch Logs Insights, la consulta de partida es:

```text
fields @timestamp, @message
| filter @message like /30000000-0000-4000-8000-000000000002/
| sort @timestamp asc
```

Copiar el `trace_id` extraído; en otra pestaña de Grafana Explore seleccionar Jaeger y el tipo de consulta **TraceID**, pegar el identificador y ejecutar. También puede buscarse directamente en Jaeger UI (`http://TASK_IP:16686`). Confirmar los spans de servidor de `orders`, cliente HTTP, servidor de `catalog` y spans SQL bajo la misma traza. Verificar visualmente que el `trace_id` del log coincide con el encabezado de traza.

**Evidencias:** `07-log-correlacionado.png` con el log y `trace_id`; `08-traza-orders-catalog.png` con la vista Jaeger/Grafana y el mismo ID; `09-correlacion-notas.txt` anotando la igualdad de IDs y los nombres de los spans observados. No incluir cuerpos de solicitud ni datos de credenciales.

### 5. Seguridad y limpieza

Desde el CIDR autorizado, comprobar que Grafana responde. Revisar en AWS que la regla del puerto 3000 contiene exactamente `allowed_cidr`. No abrir `0.0.0.0/0` para facilitar la prueba. Al terminar, ejecutar:

```sh
terraform destroy
aws ecs describe-services --region us-east-1 --cluster pipeline-otel-test --services pipeline-otel-test \
  --query 'services[0].{status:status,desired:desiredCount,running:runningCount}' --output json
```

**Evidencias:** `10-seguridad-puerto.png` con la regla CIDR enmascarando cuenta/ARN; `11-limpieza.txt` con resultado de `terraform destroy` y confirmación de que no queda una tarea del laboratorio. Si el laboratorio debe permanecer desplegado, omitir `terraform destroy`, declarar la decisión y mantener abierto el coste/limpieza en el estado de fase.

## Riesgos y bloqueantes de la fase

| Estado | Elemento | Impacto | Mitigación o siguiente acción |
|---|---|---|---|
| Abierto | Grafana aumenta el uso de memoria y costo de Fargate mientras el servicio esté activo. | Medio | Usar 1 vCPU/3 GiB en el smoke test, revisar estado `RUNNING` y destruir al terminar. |
| Abierto | Las métricas HTTP reales pueden variar de nombre/etiquetas según SDK/exporter. | Medio | Consultar muestras efectivas en Prometheus antes de fijar PromQL. |
| Abierto | El task role se comparte entre los contenedores de la tarea. | Medio | Acotar las acciones CloudWatch y ARNs de log groups a lectura de los dos grupos requeridos. |
| Abierto | Los datos de Jaeger y el filesystem de Grafana son efímeros. | Bajo | Reprovisionar desde archivos y guardar evidencia fuera de la tarea antes de destruirla. |
| Abierto | Los logs actuales muestran un error de conversión del exportador Prometheus para `pipeline_up`. | Medio | Incluirlo en el panel de errores, aislar si es recurrente y registrar el resultado; no ocultarlo en la consulta. |

## Cierre de la fase

- **Resultado obtenido:** Pendiente.
- **Desviaciones respecto al diseño:** Pendiente.
- **Decisiones tomadas durante la fase:** D-013 y D-014; agregar decisiones nuevas a `00-especificacion.md` si se requiere cambiar alcance.
- **Requisitos afectados en su cobertura:** RF-018–RF-022 y RNF-008–RNF-009 pendientes de validar.
- **Actualizaciones aplicadas a `00-plan-general.md`:** Pendiente de Gate 3.
- **Actualizaciones aplicadas a `00-especificacion.md`:** Pendiente de Gate 3.
- **Pendientes trasladados:** Pendiente.

## Referencias

- [`00-especificacion.md`](00-especificacion.md) — alcance y criterios de aceptación.
- [`00-plan-general.md`](00-plan-general.md) — enfoque y trazabilidad general.
- [`02-despliegue-ecs.md`](02-despliegue-ecs.md) — publicación, tarea y red existentes.
- [Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/) — datasources y dashboards en archivos.
- [Grafana Jaeger datasource](https://grafana.com/docs/grafana/latest/datasources/jaeger/query-editor/) — consulta de trazas por TraceID en Explore.
- [Grafana CloudWatch query editor](https://grafana.com/docs/grafana/latest/datasources/aws-cloudwatch/query-editor/) — consultas de métricas y Logs Insights.
- [AWS ECS service utilization metrics](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service_utilization.html) — métricas del servicio Fargate.
- [Tamaños Fargate CPU/memoria](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-cpu-memory-error.html) — combinaciones admitidas para Linux.
