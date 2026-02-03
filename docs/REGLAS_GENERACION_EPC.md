# Reglas de Generación de Epicrisis (EPC)

Este documento define las reglas OBLIGATORIAS que la IA debe cumplir al generar cada sección de la Epicrisis.

---

## ⛔ REGLAS CRÍTICAS - NO SE PUEDEN OMITIR

### 📋 SECCIÓN: EVOLUCIÓN

**REGLA DE FALLECIMIENTO/ÓBITO:**

Si el paciente fallece durante la internación, el ÚLTIMO PÁRRAFO de la evolución DEBE comenzar con:

```
PACIENTE OBITÓ - Fecha: DD/MM/YYYY Hora: HH:MM. [descripción]
```

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

**Ejemplo CORRECTO 1:**
```
PACIENTE OBITÓ - Fecha: 15/03/2025 Hora: 14:30. Evolucionó con shock séptico refractario a vasopresores.
```

**Ejemplo CORRECTO 2:**
```
PACIENTE OBITÓ - Fecha: 22/07/2025 Hora: hora no registrada. Presentó paro cardiorrespiratorio irreversible en contexto de falla multiorgánica.
```

**Ejemplo CORRECTO 3 (caso real):**
```
PACIENTE OBITÓ - Fecha: 29/07/2025 Hora: 22:00. Se acude a llamado de enfermería manifestando paro cardiorrespiratorio. Se intentan maniobras de reanimación sin respuesta. Se constata óbito.
```

**Ejemplo INCORRECTO (NO HACER):**
```
Evoluciona desfavorablemente y fallece.
```
↑ ¡ERROR! Falta el encabezado obligatorio.

**Otro INCORRECTO:**
```
Paciente finalmente presenta óbito.
```
↑ ¡ERROR! No tiene el formato obligatorio con fecha y hora.

---

### 📋 SECCIÓN: PROCEDIMIENTOS

**Formato obligatorio:**
```
DD/MM/YYYY HH:MM - Descripción del procedimiento
```

**Si no hay hora:**
```
DD/MM/YYYY (hora no registrada) - Descripción del procedimiento
```

**Reglas:**
- ✅ SIEMPRE incluir fecha
- ✅ Ordenar cronológicamente (fecha más antigua primero)
- ✅ Eliminar duplicados
- ❌ NUNCA escribir sin fecha

**⚠️ REGLA DE AGRUPACIÓN DE LABORATORIOS:**
Si hay múltiples estudios de laboratorio en la MISMA FECHA SIN HORA, se agrupan en una sola línea:
```
DD/MM/YYYY (hora no registrada) - 🔬 Laboratorio (5 estudios)
```
Al hacer clic se muestra el detalle: "Fosfatemia, Magnesio, Calcio iónico, Hepatograma, Ácido láctico"

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

---

### 📋 SECCIÓN: MEDICACIÓN (Plan Terapéutico)

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

**Reglas:**
- ✅ Lista de recomendaciones de seguimiento
- ❌ Si el paciente FALLECIÓ, esta sección DEBE estar VACÍA `[]`

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
28/01/2026 - v2 (Enhanced death detection)
