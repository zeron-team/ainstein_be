# 📋 Reglas de Generación de Epicrisis (EPC)

> **Versión:** 2.0  
> **Última actualización:** 2026-02-27  
> **Autor:** AInstein Engine Team  

Este documento define **todas** las reglas que el sistema aplica para generar Epicrisis (EPC).  
Las reglas se aplican en **5 capas secuenciales** durante el pipeline de generación.

---

## Arquitectura del Pipeline

```
HCE (MongoDB) → [Capa 1: Filtrado] → [Capa 2: Prompt LLM] → [Capa 3: Post-proceso] → EPC
                                                                                        ↓
                                                                              [Capa 4: PDF Export]
```

---

## 🏗️ Capa 1 — Filtrado de HCE

**Archivo:** `app/services/hce_json_parser.py`  
**Propósito:** Filtrar y estructurar los datos de la HCE ANTES de enviarlos a la IA.

### Regla 1.1 — Evolución = SOLO Evolución Médica

| Campo | Detalle |
|-------|---------|
| **Prioridad** | ⛔ CRÍTICA |
| **Descripción** | La sección "Evolución" de la EPC se construye EXCLUSIVAMENTE con registros de tipo médico |
| **Tipos válidos** | `EVOLUCION MEDICA (A CARGO)`, `INGRESO DE PACIENTE`, `PARTE QUIRURGICO`, `PARTE PROCEDIMIENTO` |
| **Tipos descartados** | `HOJA DE ENFERMERIA`, `CONTROL DE ENFERMERIA`, `BALANCE HIDROELECTROLITICO`, `EVOLUCION DE INTERCONSULTA`, `INDICACION` |
| **Justificación** | Evita que notas de enfermería (signos vitales, cambios de pañal, etc.) contaminen la evolución médica |

### Regla 1.2 — Motivo de internación ≤ 10 palabras

| Campo | Detalle |
|-------|---------|
| **Prioridad** | ⛔ CRÍTICA |
| **Descripción** | El motivo de internación se trunca automáticamente a máximo 10 palabras |
| **Formato** | Resumen lógico, sin fechas, sin nombres de paciente |
| **Ejemplo correcto** | "Fractura de cadera derecha por caída" |
| **Ejemplo incorrecto** | "Paciente de 85 años que ingresa por caída de propia altura con fractura de cadera derecha el día 15/03" |

### Regla 1.3 — Motivo nunca vacío

| Campo | Detalle |
|-------|---------|
| **Prioridad** | ⛔ CRÍTICA |
| **Descripción** | Si todas las fuentes principales están vacías, se usa la primera oración de la primera evolución médica como fallback |
| **Orden de búsqueda** | 1) `entrMotivoConsulta` → 2) Plantilla ANAMNESIS → 3) Plantilla EPICRISIS → 4) Primera evolución médica → 5) `"No especificado en HCE"` |

---

## 🤖 Capa 2 — System Prompt (Instrucciones al LLM)

**Archivo:** `app/services/ai_langchain_service.py` → `_get_epc_system_prompt()`  
**Propósito:** Instruir al LLM sobre formato, estilo y reglas obligatorias.

### Regla 2.1 — No inventar datos

> SOLO usa información presente en el texto de la HCE. NO inventes datos.  
> Si una sección no tiene información, deja el campo vacío o como lista vacía.

### Regla 2.2 — Motivo máximo 10 palabras

El LLM recibe instrucción explícita:
- Máximo 10 palabras, sin excepciones
- Resumen lógico perfecto extraído de la evolución médica
- No copiar textos largos, no incluir fechas ni nombres
- Si no hay información clara → `"No especificado en HCE"`

### Regla 2.3 — Evolución solo de fuente médica

El LLM recibe instrucción explícita:
- Usar EXCLUSIVAMENTE la sección "EVOLUCIÓN MÉDICA"
- Descartar notas de enfermería, controles, balances
- Descartar evoluciones de interconsulta (van en sección aparte)
- Estilo médico técnico, como pase entre colegas

### Regla 2.4 — Detección de Fallecimiento / OBITO

| Condición | Acción |
|-----------|--------|
| Se detecta fallecimiento en la HCE | Último párrafo de evolución **DEBE** comenzar con: `PACIENTE OBITÓ - Fecha: [fecha] Hora: [hora]. [descripción]` |
| Paciente falleció | `indicaciones_alta` = `[]` (vacías) |
| Paciente falleció | `recomendaciones` = `[]` (vacías) |

**Formato obligatorio:**
```
PACIENTE OBITÓ - Fecha: 15/03/2025 Hora: 14:30. Evolucionó con shock séptico refractario a vasopresores.
```

### Regla 2.5 — Procedimientos con fecha

- Formato: `DD/MM/YYYY HH:MM - Descripción` (o `DD/MM/YYYY (hora no registrada) - Descripción`)
- **Nunca** sin fecha
- Eliminar duplicados exactos
- Ordenar cronológicamente
- Incluir: laboratorios, imágenes, procedimientos invasivos

### Regla 2.6 — Interconsultas con fecha

- Formato: `DD/MM/YYYY HH:MM - Especialidad`
- Sin duplicados (misma fecha + misma especialidad)
- Ordenar cronológicamente

### Regla 2.7 — Clasificación de medicación

| Tipo | Descripción | Fuente en HCE |
|------|-------------|---------------|
| `previa` | Medicación que el paciente ya tomaba antes de ingresar | "antecedentes", "medicación habitual", "tratamiento crónico" |
| `internacion` | Medicación indicada durante la hospitalización | "indicaciones médicas", "plan terapéutico", "se inicia", "se indica" |

Formato JSON obligatorio:
```json
{"tipo": "internacion|previa", "farmaco": "nombre", "dosis": "cantidad", "via": "IV|Oral|SC|IM", "frecuencia": "cada X hs"}
```

---

## 🔧 Capa 3 — Post-procesamiento

**Archivo:** `app/services/ai_langchain_service.py` → `_post_process_epc_result()`  
**Propósito:** Corregir y validar el output del LLM DESPUÉS de generado.

### Regla 3.1 — Detección de fallecimiento con anti-keywords

| Categoría | Keywords | Comportamiento |
|-----------|----------|----------------|
| **Alta confianza** | `fallece`, `falleció`, `óbito`, `murió`, `deceso`, `defunción`, `exitus`, `se constata óbito`, `se certifica defunción`, `paciente finado` | Siempre detectan muerte (salvo anti-keyword fuerte cerca) |
| **Ambiguos** | `maniobras de reanimación`, `paro cardiorrespiratorio irreversible`, `retiro de soporte vital`, `limitación del esfuerzo terapéutico`, `se suspende soporte vital` | Solo detectan si NO hay anti-keyword en 200 caracteres |
| **Anti-keywords** | `revierte`, `exitosa`, `se recupera`, `estabiliza`, `mejoría`, `alta médica`, `consciente`, `vigil` | Invalidan la detección de muerte |
| **Anti-keywords fuertes** | `alta médica`, `alta sanatorial`, `se descarta`, `eventualidad`, `riesgo de`, `posibilidad de`, `podría`, `en caso de` | Invalidan incluso keywords de alta confianza |

**Archivo de implementación:** `app/rules/death_detection.py`

### Regla 3.2 — Encabezado OBITO obligatorio

Si se detecta fallecimiento y la evolución no tiene el encabezado, se inyecta automáticamente:
```
PACIENTE OBITÓ - Fecha: [fecha] Hora: [hora]. [contexto]
```

### Regla 3.3 — Eliminar frases contradictorias

Si hay OBITO, se eliminan automáticamente frases como:
- "se da de alta", "alta médica", "alta sanatorial"
- "evolución favorable", "buena evolución"
- "se retira deambulando", "egreso a domicilio"
- "controles ambulatorios", "seguimiento ambulatorio"

### Regla 3.4 — Interconsultas y procedimientos sin fecha

- Se descartan interconsultas sin fecha
- Se descartan procedimientos sin fecha
- Se normalizan fechas `YYYY-MM-DD` → `DD/MM/YYYY`

### Regla 3.5 — Agrupación de hemodiálisis

Múltiples sesiones de hemodiálisis se agrupan en una sola entrada:
```
15/01/2025 - Hemodiálisis (8 sesiones del 15/01/2025 al 28/01/2025)
```

### Regla 3.6 — Reclasificación de medicación

| Si es... | Y está marcado como... | Se corrige a... |
|----------|----------------------|-----------------|
| Antihipertensivo oral (losartán, enalapril, etc.) | `internacion` | `previa` |
| Antibiótico IV (vancomicina, meropenem, etc.) | `previa` | `internacion` |

### Regla 3.7 — Motivo máximo 10 palabras (refuerzo)

Se aplica un truncamiento hard-coded a 10 palabras como safety net, incluso si el LLM generó más.

### Regla 3.8 — Motivo nunca vacío (refuerzo)

Si después de todo el pipeline el motivo está vacío → `"No especificado en HCE"`.

---

## 📄 Capa 4 — Exportación PDF

**Archivo:** `app/utils/epc_pdf.py` → `_coalesce_sections()`  
**Propósito:** Controlar qué secciones aparecen en el PDF exportado.

### Regla 4.1 — Orden de secciones en PDF

```
1. Título
2. Datos clínicos
3. Motivo de internación
4. Evolución
5. Procedimientos
6. Interconsultas
7. Indicaciones de alta
```

### Regla 4.2 — Secciones excluidas del PDF

Las siguientes secciones **NO** aparecen en el PDF:

| Excluida | Motivo |
|----------|--------|
| Plan Terapéutico | La medicación es información interna, no para el PDF de epicrisis |
| Tratamiento / Medicación | Ídem |
| Medicación | Ídem |
| Notas al Alta | Información interna |
| Recomendaciones | Información interna |

---

## 🛡️ Capa 5 — Módulo de Death Detection

**Archivo:** `app/rules/death_detection.py`  
**Propósito:** Detección autónoma de fallecimiento con minimización de falsos positivos.

### Funciones exportadas

| Función | Uso |
|---------|-----|
| `detect_death_in_text(text)` | Detecta fallecimiento en texto libre. Retorna `DeathInfo` |
| `detect_death_from_alta_type(tipo_alta)` | Detecta fallecimiento desde el campo `taltDescripcion` del episodio |
| `format_death_line(date, time, description)` | Genera línea formateada de OBITO |

### Dataclass `DeathInfo`

```python
@dataclass
class DeathInfo:
    detected: bool          # ¿Se detectó fallecimiento?
    date: Optional[str]     # Fecha extraída (DD/MM/YYYY)
    time: Optional[str]     # Hora extraída (HH:MM)
    source_text: Optional[str]      # Fragmento de texto fuente
    detection_method: Optional[str]  # Método usado (keyword:xxx)
```

---

## 📝 Historial de Cambios

| Fecha | Versión | Cambio |
|-------|---------|--------|
| 2026-02-27 | 2.0 | Reglas de Oro: filtrado EVOLUCIÓN MÉDICA, motivo 10 palabras, anti-keywords death detection, PDF sin medicación |
| 2025-12-01 | 1.0 | Versión inicial con reglas de OBITO, procedimientos, interconsultas |
