# Reglas de Generación de Epicrisis (EPC)

Este documento define las reglas OBLIGATORIAS que la IA debe cumplir al generar cada sección de la Epicrisis.

---

## 🎯 TABLA DE DECISIÓN RÁPIDA - CLASIFICACIÓN DE SECCIONES

> **Regla de Oro**: 
> - Si el acto principal es "**mirar/medir**" sin invadir → **Estudio**
> - Si el acto principal es "**hacer**" invasivo/intervencionista → **Procedimiento**
> - Si el acto principal es "**opinar/evaluar**" por otra especialidad → **Interconsulta**
> - Si es análisis de muestras biológicas → **Laboratorio**

| Categoría | Ejemplos | Sección Correcta |
|-----------|----------|------------------|
| **Imágenes** | Rx, Eco, TAC, RM, mamografía, densitometría | **Estudios Complementarios** |
| **Funcionales no invasivos** | ECG, Holter, MAPA, PEG, Ecocardiograma, EEG | **Estudios Complementarios** |
| **Endoscópicos** | VEDA, colonoscopía, broncoscopía, CPRE | **Procedimientos** |
| **Invasivos/Intervencionistas** | Biopsia, punción, cateterismo, CVC, intubación | **Procedimientos** |
| **Terapéuticos invasivos** | Transfusión, diálisis, cardioversión, RCP | **Procedimientos** |
| **Evaluaciones por especialidad** | "Visto por Cardio/Infecto/Neuro indica..." | **Interconsultas** |
| **Análisis de muestras** | Hemograma, urea, creatinina, PCR, hemocultivos | **Laboratorio** |

---

## ⛔ REGLAS CRÍTICAS - NO SE PUEDEN OMITIR

### 📋 SECCIÓN: EVOLUCIÓN

**REGLA DE FALLECIMIENTO/ÓBITO:**

Si el paciente fallece durante la internación, la evolución debe tener esta estructura:

1. **PRIMERO**: Describir TODA la evolución clínica durante la internación
2. **AL FINAL**: Agregar una SUBSECCIÓN SEPARADA con el siguiente formato:

```
[... texto de evolución incluyendo circunstancias del fallecimiento ...]

---
**DESENLACE: ÓBITO**
Fecha: DD/MM/YYYY | Hora: HH:MM
---
```

**⚠️ REGLAS CRÍTICAS:**
- El bloque de ÓBITO debe estar **SIEMPRE AL FINAL** de la evolución
- Debe estar **SEPARADO** del resto del texto por líneas en blanco
- **SOLO** incluir fecha y hora, SIN descripción (la descripción ya está en la evolución)
- **NUNCA** mezclar el texto de ÓBITO con los párrafos de evolución clínica

**Palabras clave que activan esta regla:**
- fallece, falleció, fallecio, falleciendo
- óbito, obito, obitó, éxitus, exitus
- murió, murio, deceso
- defunción, defuncion, fallecimiento
- muerte, muerto, finado, fallecido
- paro cardiorrespiratorio (con o sin "irreversible"), PCR
- fin de vida (en contexto de fallecimiento)
- se suspende soporte vital, se certifica defunción
- retiro de soporte vital, limitación del esfuerzo terapéutico
- **constata, se constata** (común en: "se constata óbito")
- **maniobras de reanimación** (indica intento de RCP)

**Ejemplo CORRECTO:**
```
Paciente de 79 años, sexo masculino, con antecedentes de HTA, DLP, FA...
Durante la internación se realizan estudios complementarios...
Evoluciona con deterioro progresivo del sensorio y falla multiorgánica.
El paciente presenta paro cardiorrespiratorio que no responde a maniobras
de reanimación. Se constata óbito.

---
**DESENLACE: ÓBITO**
Fecha: 26/01/2026 | Hora: 14:30
---
```

**Ejemplo INCORRECTO (NO HACER):**
```
Paciente de 79 años... PACIENTE OBITÓ - Fecha: 26/01/2026 Hora: hora no
registrada. Durante la internación se realizan estudios...
```
↑ ¡ERROR! ÓBITO está mezclado con el texto de evolución, no al final.

---

### 📋 SECCIÓN: PROCEDIMIENTOS REALIZADOS

**DEFINICIÓN:**
> **PROCEDIMIENTO (EPC)**: Toda intervención diagnóstica o terapéutica efectivamente realizada al paciente durante el episodio asistencial, que implique una acción clínica identificable, con fecha/hora aproximada, responsable/servicio, y resultado inmediato o incidencia.
> Incluye procedimientos invasivos y no invasivos, quirúrgicos, endoscópicos, intervencionistas, y maniobras terapéuticas relevantes.

---

#### ✅ QUÉ INCLUIR (Ejemplos obligatorios):

| Categoría | Ejemplos |
|-----------|----------|
| **Quirúrgicos** | Cirugía mayor/menor, toilette, sutura, drenaje, desbridamiento |
| **Intervencionistas** | Cateterismo, angioplastia, colocación de stent, biopsia guiada |
| **Endoscópicos** | **VEDA** (Videoendoscopía Digestiva Alta), colonoscopía, broncoscopía, CPRE |
| **Dispositivos/Accesos** | Vía central, PICC, sonda vesical, SNG, intubación (IOT), traqueostomía |
| **Terapéuticos** | Transfusión, diálisis, ventilación mecánica, cardioversión, RCP |
| **Diagnósticos relevantes** | Punción lumbar, artrocentesis, toracocentesis, paracentesis |

---

#### ❌ QUÉ NO ES PROCEDIMIENTO (NO incluir):

| NO incluir | Va en... |
|------------|----------|
| Medicaciones (ATB, analgesia, etc.) | **Plan Terapéutico / Farmacológica** |
| Laboratorio rutinario | **Estudios Complementarios** |
| Rx simple (sin intervención) | **Estudios Complementarios** |
| Conductas generales ("observación", "control evolutivo") | **Evolución** |
| Diagnósticos | **Diagnóstico de ingreso/egreso** |

---

#### 📋 REGLAS OBLIGATORIAS:

1. ✅ **Listar SOLO lo realizado** (no lo indicado ni lo planificado)
2. ✅ **Cada procedimiento DEBE incluir**:
   - Nombre estándar (si usa sigla, aclararla: ej. "VEDA (Videoendoscopía Digestiva Alta)")
   - Fecha y hora
   - Servicio/área (quirófano, UTI, guardia, hemodinamia, endoscopía)
   - Motivo (breve)
   - Hallazgos/resultado
   - Complicaciones (si hubo)
3. ✅ **Ordenar cronológicamente** (fecha más antigua primero)
4. ❌ **Si NO hubo procedimientos**: Escribir exactamente:
   ```
   No se registran procedimientos invasivos/intervencionistas durante la internación.
   ```

---

#### 📌 FORMATO OBLIGATORIO:

```
DD/MM/YYYY HH:MM - [Servicio] Nombre del procedimiento
  • Motivo: ...
  • Hallazgos: ...
  • Complicaciones: ninguna / descripción
```

**Ejemplo CORRECTO:**
```
15/01/2026 10:30 - [Endoscopía] VEDA (Videoendoscopía Digestiva Alta)
  • Motivo: Hemorragia digestiva alta
  • Hallazgos: Úlcera gástrica Forrest IIb, se realiza esclerosis
  • Complicaciones: ninguna

16/01/2026 14:00 - [UTI] Intubación orotraqueal (IOT)
  • Motivo: Insuficiencia respiratoria aguda
  • Hallazgos: Vía aérea difícil, se logra al segundo intento
  • Complicaciones: ninguna
```

---

**⚠️ REGLA DE AGRUPACIÓN DE LABORATORIOS:**
Si hay múltiples estudios de laboratorio en la MISMA FECHA SIN HORA, se agrupan en una sola línea:
```
DD/MM/YYYY (hora no registrada) - 🔬 Laboratorio (5 estudios)
```

---

### 📋 SECCIÓN: INTERCONSULTAS

**Formato obligatorio:**
```
DD/MM/YYYY HH:MM - Especialidad
```

**Si no hay hora:**
```
DD/MM/YYYY (hora no registrada) - Especialidad
```

**Reglas:**
- ✅ SIEMPRE incluir fecha
- ✅ Ordenar cronológicamente (fecha más antigua primero)
- ✅ Eliminar duplicados exactos
- ❌ NUNCA escribir sin fecha

**⚠️ REGLA DE AGRUPACIÓN POR ESPECIALIDAD:**
Las interconsultas se agrupan por especialidad, mostrando **SOLO la PRIMERA fecha/hora** de cada especialidad.

**Ejemplo:**
Si hay 3 interconsultas a Infectología:
- 13/01/2026 10:00 - Infectología
- 14/01/2026 14:00 - Infectología  
- 15/01/2026 09:00 - Infectología

El resultado agrupado es:
```
13/01/2026 10:00 - Infectología
```
(Solo aparece la primera fecha, las demás se omiten)

**Especialidades detectadas automáticamente:**
- Cardiología, Neurología, Nefrología, Cirugía General
- Traumatología, Hematología, Infectología, Neumonología
- Kinesiología, Gastroenterología, Endocrinología
- Urología, Otorrinolaringología, Dermatología
- Psiquiatría, Psicología, Nutrición, Cuidados Paliativos
- Clínica Médica (default)

---

### 📋 SECCIÓN: ESTUDIOS COMPLEMENTARIOS (No Laboratoriales)

**DEFINICIÓN:**
> Todo estudio diagnóstico realizado para obtener información clínica durante el episodio, que **NO sea laboratorio** y que **NO implique un procedimiento invasivo/intervencionista** como acto principal.

---

#### ✅ QUÉ INCLUIR:

| Categoría | Ejemplos |
|-----------|----------|
| **Imágenes** | Rx, ecografía, Doppler, TAC, RMN, mamografía, densitometría |
| **Cardiológicos/Funcionales no invasivos** | ECG, Holter, MAPA, prueba ergométrica (PEG), ecocardiograma transtorácico (ETT) |
| **Neurológicos/Funcionales** | EEG, EMG, potenciales evocados |
| **Respiratorios** | Espirometría |
| **Otros no invasivos** | Audiometría, campimetría |

---

#### ❌ QUÉ NO INCLUIR (va en otras secciones):

| NO incluir | Va en... |
|------------|----------|
| Laboratorio (hemograma, bioquímica, cultivos) | **Laboratorio** |
| Endoscopías (VEDA, colonoscopía, broncoscopía) | **Procedimientos** |
| Punciones/Biopsias | **Procedimientos** |
| Interconsultas con especialistas | **Interconsultas** |

---

#### 📋 REGLAS OBLIGATORIAS:

1. ✅ Listar SOLO estudios diagnósticos no laboratoriales realizados
2. ✅ Excluir: laboratorio, procedimientos invasivos, interconsultas
3. ✅ Cada estudio debe incluir: **Tipo de estudio** + **Fecha**
4. ❌ Si NO hubo estudios: "No se registran estudios complementarios no laboratoriales."
5. ⚠️ Si dato incompleto: "sin informe disponible" (NO inventar resultados)

---

#### 📌 FORMATO OBLIGATORIO:

```
DD/MM/YYYY — Tipo de estudio
```

**Ejemplo CORRECTO:**
```
05/02/2026 — TAC de cráneo sin contraste
06/02/2026 — Ecocardiograma transtorácico (ETT)
07/02/2026 — Rx de tórax frente
```

---

### 📋 SECCIÓN: LABORATORIO

**DEFINICIÓN:**
> Todos los análisis de muestras biológicas realizados durante el episodio (sangre, orina, cultivos, etc.).

---

#### ✅ QUÉ INCLUIR:

| Categoría | Ejemplos |
|-----------|----------|
| **Hematología** | Hemograma, plaquetas, coagulación, TP, KPTT |
| **Bioquímica** | Glucemia, urea, creatinina, ionograma, hepatograma |
| **Marcadores** | PCR, procalcitonina, troponina, BNP |
| **Microbiología** | Hemocultivos, urocultivo, coprocultivo |
| **Gases** | Gasometría arterial/venosa |

---

#### ❌ QUÉ NO ES LABORATORIO:

| NO incluir | Va en... |
|------------|----------|
| Estudios de imágenes (Rx, TAC, Eco) | **Estudios Complementarios** |
| Estudios funcionales (ECG, EEG) | **Estudios Complementarios** |

---

#### 📋 REGLAS:

- ✅ Agrupar por fecha si hay múltiples estudios
- ✅ Ordenar cronológicamente
- ❌ Si no hay: "No se registran determinaciones de laboratorio."

---

**Formato obligatorio (JSON):**
```json
{
  "tipo": "internacion" | "previa",
  "farmaco": "Nombre del medicamento",
  "dosis": "Cantidad",
  "via": "IV | Oral | SC | IM",
  "frecuencia": "cada X hs"
}
```

**Reglas:**
- ✅ Campo "tipo" es OBLIGATORIO
- `internacion` = administrada DURANTE la hospitalización
- `previa` = medicación habitual del paciente ANTES de ingresar (antecedentes, tratamiento crónico)

**⚠️ VERIFICACIÓN AUTOMÁTICA (Post-Procesamiento):**
El sistema CORRIGE automáticamente clasificación incorrecta basándose en:

**Medicamentos típicamente PREVIOS (crónicos orales):**
- Antihipertensivos: losartan, valsartan, enalapril, amlodipino, bisoprolol
- Estatinas: atorvastatina, simvastatina, rosuvastatina
- Diabetes: metformina, glibenclamida
- Tiroides: levotiroxina
- IBP: omeprazol, pantoprazol

**Medicamentos típicamente de INTERNACIÓN (agudos IV):**
- Antibióticos IV: ampicilina/sulbactam, piperacilina/tazobactam, vancomicina
- Analgésicos: morfina, fentanilo
- Vasopresores: noradrenalina, dopamina
- Otros: furosemida IV, amiodarona

---

### 📋 SECCIÓN: INDICACIONES AL ALTA

**Reglas:**
- ✅ Lista de indicaciones para el paciente al alta
- ❌ Si el paciente FALLECIÓ, esta sección DEBE estar VACÍA `[]`

---

### 📋 SECCIÓN: RECOMENDACIONES

**Reglas Fundamentales:**
- ✅ Lista de recomendaciones de seguimiento
- ❌ Si el paciente FALLECIÓ, esta sección DEBE estar VACÍA `[]`
- ✅ Las recomendaciones deben basarse en la EVOLUCIÓN del paciente

---

#### ✅ REGLAS DE ESTILO MÉDICO:

1. **Redactar con ROL MÉDICO** y léxico profesional
2. Usar **terminología médica precisa** y formal
3. Recomendaciones **personalizadas** según la evolución clínica

---

#### ⛔ ERRORES COMUNES A EVITAR:

| ❌ INCORRECTO | ✅ CORRECTO | Razón |
|--------------|-------------|-------|
| "Consultar si fiebre mayor a 38°C" | "Control precoz ante temperatura ≥38°C o deterioro del estado general" | Fiebre YA es >38°C (redundante) |
| "Control si presenta fiebre" | "Consulta precoz ante hipertermia o signos de infección" | Impreciso |
| "Tomar medicación según indicación" | "Cumplir tratamiento antibiótico por 7 días según esquema indicado" | Genérico |
| "Hacer reposo" | "Reposo relativo con movilización progresiva según tolerancia" | Vago |
| "Controlar herida" | "Curación de herida quirúrgica cada 48hs con solución fisiológica" | Sin especificar |

---

#### 📋 ESTRUCTURA DE RECOMENDACIONES:

1. **Controles clínicos específicos** (qué monitorear y cuándo)
2. **Signos de alarma claros** (cuándo consultar urgente)
3. **Seguimiento por especialidades** según interconsultas realizadas
4. **Indicaciones de actividad física/dieta** si aplica
5. **Controles de estudios pendientes** si corresponde

---

---

## ⚠️ Nota Importante sobre Detección de Fallecimiento

El sistema tiene múltiples mecanismos para detectar fallecimiento:
1. **Detección por IA**: El modelo analiza el texto y debe aplicar la regla automáticamente
2. **Post-procesamiento**: Un script backend verifica y corrige si la IA falló

Si aún así encuentras casos donde no se aplica correctamente, reporta el caso con:
- El texto completo de la HCE
- La palabra o frase exacta que indica fallecimiento
- El resultado generado

---

## Última actualización
06/02/2026 - v3.0
- Agregada Tabla de Decisión Rápida (Regla de Oro)
- Nueva sección: Estudios Complementarios (no laboratoriales)
- Nueva sección: Laboratorio
- Actualizado filtrado de procedimientos (endoscopías, ablación)
- Mejorado léxico médico en Recomendaciones
