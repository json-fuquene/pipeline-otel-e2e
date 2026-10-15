# Comparación de overhead OpenTelemetry

Las cifras se calculan como la mediana entre rondas válidas. CPU/memoria son promedios de muestras `docker stats` durante la medición; memoria se refiere al uso reportado por Docker CLI en este host.

| API | Métrica | Base | OTel | Diferencia | Diferencia relativa |
|---|---|---:|---:|---:|---:|
| catalog | HTTP p99 | 3.294 ms | 26.890 ms | 23.596 ms | 716.210% |
| catalog | CPU promedio | 0.837% | 7.797% | 6.960 p.p. | 831.045% |
| catalog | Memoria promedio | 73.712 MiB | 73.450 MiB | -0.263 MiB | -0.356% |
| orders | HTTP p99 | 4.061 ms | 5.546 ms | 1.485 ms | 36.576% |
| orders | CPU promedio | 6.417% | 7.445% | 1.028 p.p. | 16.011% |
| orders | Memoria promedio | 77.082 MiB | 76.685 MiB | -0.398 MiB | -0.516% |

Rondas válidas: 2 de 2. Los resultados `N/D` significan que no hubo suficientes rondas válidas o que el denominador fue cero.
