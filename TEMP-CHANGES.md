# Cambios temporales de la sesión de pruebas

| Ruta | Cambio | Motivo | Reversión |
|---|---|---|---|
| `/tmp/pipeline-chaos-phase3-session.py` | Orquestador de pruebas con imágenes locales fijadas | Ejecutar fase3-01 sin builds ni descargas; montar supervisor actual | Eliminar al finalizar la sesión |
| `/tmp/pipeline-chaos-phase3-override.json` | Override Compose temporal con imágenes locales y montaje del supervisor | Aislar la variante de validación sin editar el manifiesto del proyecto | Eliminar después de detener el proyecto de pruebas |

Los artefactos de `artifacts/chaos/fase3-01/`, las credenciales privadas y el volumen del ensayo se conservarán para revisión; no se eliminan como parte de esta reversión.
