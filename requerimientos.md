Diseñar y ejecutar, en un entorno simulado, un programa de *Chaos Engineering* que fortalezca la resiliencia de los sistemas distribuidos. Aplicar los principios de antifragilidad de SRE y el marco de *Game Days* para detectar debilidades sistémicas antes de que se manifiesten en producción.

## Actividades

1. Formular tres hipótesis de fallo con el formato: «En estado estable, cuando [condición], esperamos que [comportamiento del sistema]» (metodología de los Principios del Caos).
2. Diseñar tres experimentos de caos correspondientes. Para cada uno, especificar el tipo de fallo (latencia, error, agotamiento de recursos o partición de red), el radio de impacto, la duración y la reversión automática.
3. Definir las métricas de observabilidad para verificar cada hipótesis: qué SLI medirá el impacto y qué registros o trazas confirmarán el comportamiento esperado.
4. Ejecutar un experimento en un entorno local (usando `tc netem` para introducir latencia de red o `stress-ng` para generar estrés de CPU) y documentar los resultados reales.
5. Reflexionar: ¿Qué debilidad sistémica reveló el experimento? ¿Qué remediación se propone?

## Entregable

Un plan de *Game Day* en PDF (4–5 páginas) que incluya las hipótesis de fallo, los experimentos de caos diseñados (usando conceptualmente Chaos Monkey, Gremlin o Litmus), las métricas de observabilidad para verificar las hipótesis y un análisis de los resultados esperados frente a los obtenidos en un experimento ejecutable en un entorno local o *sandbox*.