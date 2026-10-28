# Integración del skill `redactar-cuartilla-investigacion` con opencode

opencode tiene **soporte nativo de agent skills**: descubre ficheros `SKILL.md` (con
frontmatter YAML `name` + `description`) desde tu repositorio o tu carpeta de
configuración, y el agente los carga bajo demanda mediante su herramienta de skills cuando
son relevantes o cuando los invocas explícitamente. Referencia oficial:
`https://opencode.ai/docs/skills/`.

Un skill es **una carpeta con un `SKILL.md`** dentro. En este paquete ya está en:

```
.opencode/skills/redactar-cuartilla-investigacion/SKILL.md
```

## Opción A — Proyecto (recomendada para este paquete)

Si abres la carpeta `mineria-texto-sca2/` como proyecto en opencode, el skill en
`.opencode/skills/` se descubre **automáticamente**. No hay que copiar nada.

```bash
cd mineria-texto-sca2
opencode            # abre opencode en este directorio
```

Los skills del proyecto (`.opencode/skills/`) tienen **prioridad** sobre los globales.

## Opción B — Instalación global (para usarlo en cualquier proyecto)

Copia la carpeta del skill a una de las ubicaciones globales que opencode escanea:

```bash
mkdir -p ~/.config/opencode/skills
cp -r .opencode/skills/redactar-cuartilla-investigacion ~/.config/opencode/skills/
```

Ubicaciones de descubrimiento (de menor a mayor prioridad):

1. `~/.config/opencode/skills/<id>/SKILL.md`  (global, XDG)
2. `~/.opencode/skills/<id>/SKILL.md`          (global)
3. `$OPENCODE_CONFIG_DIR/skills/<id>/SKILL.md` (si la variable está definida)
4. `.opencode/skills/<id>/SKILL.md`            (proyecto — máxima prioridad)

> **Reinicia opencode** tras añadir o modificar un skill para que lo vuelva a escanear.

## Frontmatter del skill

opencode reconoce estos campos en el `SKILL.md` (ya incluidos en este skill):

```yaml
---
name: redactar-cuartilla-investigacion      # requerido (único en todas las ubicaciones)
description: >-                               # requerido (define cuándo usarlo)
  Usar cuando se pida redactar una cuartilla a partir de la materia prima...
compatibility: opencode                       # opcional
metadata:                                      # opcional (string -> string)
  opencode/autoinvoke: "true"                 # el modelo lo ve en su guía y puede auto-usarlo
  opencode/slash: "true"                      # expone un comando de barra (/redactar-...)
---
```

- `description` es lo que el agente usa para decidir cuándo cargar el skill: mantenla
  precisa (incluye los disparadores: "redacta la cuartilla", ficheros `materia_prima.md`...).
- Pon el comportamiento específico de opencode en `metadata` (no añadas campos propios de
  primer nivel).

## Cómo usarlo (flujo completo)

1. Genera la materia prima con el pipeline:

   ```bash
   python run_pipeline.py data/corpus_mra.csv -o salida_mra --title "Corpus MRA"
   ```

2. En opencode, pídele al agente que use el skill sobre la materia prima:

   ```
   Usando el skill redactar-cuartilla-investigacion, analiza salida_mra/materia_prima.md
   y redacta la cuartilla.
   ```

   - Si `opencode/slash: "true"`, también puedes invocarlo con el comando de barra que
     opencode genere a partir del nombre del skill.
   - El agente cargará el `SKILL.md`, leerá `materia_prima.md` y devolverá la cuartilla
     más una nota de trazabilidad (qué sección respalda cada parte).

## Permisos

opencode controla el acceso a skills con `permission` en `opencode.json`. Un skill con
permiso `deny` queda **oculto** para el agente. Si no aparece, revisa que el permiso no lo
esté bloqueando.

## Resolución de problemas

- **No aparece el skill:** el fichero debe llamarse exactamente `SKILL.md` (en mayúsculas);
  el `name` debe ser único entre todas las ubicaciones; reinicia opencode.
- **No se auto-invoca:** revisa `metadata["opencode/autoinvoke"]` (los puestos a `"false"`
  se ocultan de la guía del modelo) y los permisos del agente.
- **Rutas dentro del skill:** son relativas a la carpeta que contiene el `SKILL.md`.

## Fallback para otros agentes

El `SKILL.md` sigue el estándar abierto *Agent Skills* (frontmatter `name` + `description`
+ instrucciones en Markdown), compatible también con:

- **Claude Code:** coloca la carpeta en `~/.claude/skills/redactar-cuartilla-investigacion/`.
- **Codex / agentes con el estándar Agent Skills:** ubicaciones `.agents/skills/` o el
  *fallback* `AGENTS.md`.
- **Cualquier agente sin soporte de skills:** pega el contenido de `SKILL.md` como
  instrucción/contexto del sistema al pedir la redacción, junto con `materia_prima.md`.
