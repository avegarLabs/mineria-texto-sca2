---
name: redactar-cuartilla-investigacion
description: >-
  Usar cuando se pida redactar una CUARTILLA de investigación (justificación o
  introducción de una página) a partir de un fichero markdown de "materia prima"
  generado por mineria_texto.py / run_pipeline.py. Dispara con peticiones como
  "escribe/redacta la cuartilla", "redacta la justificación", "convierte esta materia
  prima en una cuartilla", o cuando se entrega un .md con secciones del tipo "Materia
  prima para redactar la cuartilla", "Términos clave", "Temas detectados",
  "Intersecciones poco exploradas (candidatas a brecha)". No usar para escribir el
  manuscrito completo ni para análisis estadístico; solo para la cuartilla a partir de
  la evidencia minada.
compatibility: opencode
metadata:
  audience: investigadores
  workflow: mineria-de-texto
  opencode/autoinvoke: "true"
  opencode/slash: "true"
---

# Redactar una cuartilla de investigación desde la materia prima de minería de texto

## Propósito

Transformar el esqueleto `.md` producido por `mineria_texto.py` / `run_pipeline.py`
(evidencia extraída de un corpus bibliográfico) en una **cuartilla** de justificación de
la investigación: un único bloque de prosa (~250–300 palabras), en español académico,
fundamentada exclusivamente en esa evidencia.

## Entrada esperada

El fichero de materia prima (p. ej. `salida/materia_prima.md`), con estas secciones:
1. Resumen del corpus · 2. Términos clave · 3. Temas detectados (con documentos
representativos) · 4. Red de co-ocurrencia · 5. Intersecciones poco exploradas
(candidatas a brecha) · 6. Tendencia temporal · 7. Instrucciones para el LLM.

Si no se ha proporcionado el fichero, pídelo o búscalo en el directorio de trabajo
(p. ej. `**/materia_prima.md` o `esqueleto_cuartilla*.md`). No redactes sin él.

## Procedimiento

1. **Lee y analiza** las secciones 1–6 del `.md`. Extrae:
   - **Contexto** (sección 1 y dominio del corpus): el fenómeno/enfermedad y la
     limitación del método o escala de referencia que motiva el estudio.
   - **Hilos del estado del arte** (secciones 2 y 3): resume cada tema en una idea; usa
     los términos clave como vocabulario del campo y, si ayudan, apóyate en los
     documentos representativos (sin citarlos como referencias formales).
   - **Brecha** (sección 5 y lo ausente entre los temas de la sección 3): las
     intersecciones poco exploradas (términos frecuentes que casi no co-ocurren) son la
     evidencia objetiva del vacío de conocimiento.
   - **Tendencia** (sección 6) solo si aporta (campo emergente/reciente).
2. **Formula el objetivo** como respuesta directa a esa brecha.
3. **Redacta la cuartilla** con la estructura de abajo.
4. **Aplica la lista de verificación** antes de entregar.

## Estructura de la cuartilla (cuatro movimientos, en prosa continua)

1. **Contexto del problema** — la enfermedad/fenómeno y por qué el método o escala
   actual es insuficiente.
2. **Estado del arte sintetizado** — 2–3 frases que integran los temas detectados,
   mencionando los términos clave como ejes del campo.
3. **Brecha** — enunciada de forma explícita, apoyada en las intersecciones poco
   exploradas y en lo ausente entre los temas.
4. **Objetivo** — el objetivo de la investigación que cubre esa brecha.

## Reglas de redacción (estrictas)

- **No inventar nada.** Usa solo lo que aparece en la materia prima. Prohibido añadir
  cifras, porcentajes, fechas, autores o citas que no estén en el fichero.
- Si un dato es necesario pero no está en la evidencia, **no lo inventes**: déjalo como
  marcador `[VERIFICAR: …]` o reformula para no necesitarlo.
- Los temas y términos deben provenir de las secciones 2–3; no introduzcas conceptos que
  el corpus no respalde.
- **Longitud:** ~250–300 palabras. **Formato:** prosa continua, sin títulos ni viñetas.
- **Tono:** académico, impersonal, en español; sin superlativos no respaldados.
- Brecha y objetivo **coherentes**: el objetivo responde exactamente a la brecha.

## Lista de verificación antes de entregar

- [ ] ¿Toda afirmación se sostiene en la materia prima (secciones 1–6)?
- [ ] ¿La brecha procede de la sección 5 / de lo ausente, y no de una suposición?
- [ ] ¿El objetivo responde a esa brecha?
- [ ] ¿Sin cifras ni citas inventadas? ¿Los datos no disponibles van como `[VERIFICAR]`?
- [ ] ¿Entre 250 y 300 palabras, en un solo bloque de prosa?
- [ ] ¿Vocabulario tomado de los términos/temas detectados?

## Salida

1. **La cuartilla** (el párrafo final).
2. Una **nota de trazabilidad** (fuera de la cuartilla): qué sección respalda cada uno de
   los cuatro movimientos, y la lista de `[VERIFICAR]` si los hay.

## Ejemplo (resumido)

**Materia prima (extracto):** Términos clave: ataxia, pose, estimation, mediapipe, gait.
Temas: (1) clínica/genética de ataxias; (2) evaluación motora por vídeo; (3) estimación de
pose sin marcadores. Brecha: "ataxia × pose" co-ocurren en 0 documentos (lift=0.0).

**Cuartilla (salida):** "La ataxia espinocerebelosa es un trastorno neurodegenerativo cuya
evaluación motora depende de escalas clínicas ordinales y dependientes del observador. La
literatura reciente muestra tres líneas: la caracterización clínica y genética de las
ataxias, la evaluación motora basada en vídeo y la estimación de pose sin marcadores
(MediaPipe). Sin embargo, estas líneas apenas se cruzan: los términos 'ataxia' y
'estimación de pose' casi no coinciden en un mismo trabajo, lo que revela que la visión
computacional no se ha aplicado de forma sistemática a la cuantificación motora en la
ataxia. Esta investigación tiene por objetivo desarrollar y validar un sistema de visión
computacional sin marcadores que cuantifique de forma objetiva los signos motores de la
ataxia, cubriendo ese vacío." *(Trazabilidad: contexto←§1; estado del arte←§2–3;
brecha←§5; objetivo←síntesis.)*
