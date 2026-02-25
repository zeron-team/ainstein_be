"""
EPC Prompts - Prompts específicos por sección de la Epicrisis

Cada sección de la EPC tiene su propio prompt con reglas clínicas específicas:
- Motivo de Internación
- Evolución (incluye regla de óbito)
- Procedimientos
- Interconsultas  
- Plan Terapéutico (medicación)

IMPORTANTE: Estos prompts están diseñados para Gemini 2.0 Flash con temperature=0.1
"""

from langchain_core.prompts import PromptTemplate


# =============================================================================
# SECCIÓN 1: MOTIVO DE INTERNACIÓN
# =============================================================================

PROMPT_MOTIVO_INTERNACION = PromptTemplate(
    template="""Analiza el siguiente registro de INGRESO DE PACIENTE y extrae el motivo principal de internación.

REGLAS OBLIGATORIAS:
1. Responde en 1-2 frases concisas
2. Usa lenguaje médico técnico
3. NO inventes datos que no estén en el texto
4. Si hay múltiples motivos, prioriza el principal
5. Responde SOLO con JSON válido

CONTEXTO - INGRESO:
{ingreso_text}

EDAD: {edad} años
SEXO: {sexo}

RESPONDE SOLO CON:
{{"motivo_internacion": "..."}}
""",
    input_variables=["ingreso_text", "edad", "sexo"]
)


# =============================================================================
# SECCIÓN 2: EVOLUCIÓN (+ REGLA DE ÓBITO)
# =============================================================================

PROMPT_EVOLUCION = PromptTemplate(
    template="""Genera la sección EVOLUCIÓN de la epicrisis basándote en las evoluciones médicas.

{instruccion_obito}

TIPO DE ALTA OFICIAL DEL EPISODIO: {tipo_alta_oficial}

REGLAS OBLIGATORIAS:
1. Iniciar con: "Paciente de {edad} años, sexo {sexo}, ..."
2. Narrativa cronológica desde ingreso hasta egreso/óbito
3. Lenguaje técnico médico, estilo pase entre colegas
4. Describir: antecedentes → ingreso → evaluación → tratamiento → evolución → desenlace
5. NO mencionar fármacos específicos (van en Plan Terapéutico)
6. 2-4 párrafos coherentes
7. USA SOLO LA INFORMACIÓN DEL CONTEXTO - NO INVENTES DATOS

⛔⛔⛔ REGLA CRÍTICA DE FALLECIMIENTO - NO NEGOCIABLE ⛔⛔⛔

SI el TIPO DE ALTA es "OBITO" o similar, O si en el texto aparecen palabras de fallecimiento:
- "fallece", "falleció", "óbito", "obito", "obitó", "exitus"
- "murió", "defunción", "constata óbito"
- "paro cardiorrespiratorio", "pcr"

ENTONCES el ÚLTIMO PÁRRAFO OBLIGATORIAMENTE DEBE comenzar con:

"PACIENTE OBITÓ - Fecha: {{fecha_egreso}} Hora: {{hora}}. {{descripción}}"

⚠️ SI tipo_alta = OBITO, NO puedes mencionar:
- "alta a domicilio"
- "se retira deambulando"  
- "evolución favorable con alta"
- "mejoría... se decide alta"

Estos términos SON CONTRADICTORIOS con OBITO.

EJEMPLOS CORRECTOS PARA OBITO:
✓ "PACIENTE OBITÓ - Fecha: 21/01/2024 Hora: 18:32. Se constata óbito."
✓ "PACIENTE OBITÓ - Fecha: 21/01/2024 Hora: 18:32. Evolucionó desfavorablemente."

CONTEXTO - EVOLUCIONES MÉDICAS:
{evoluciones_text}

CONTEXTO - INGRESO:
{ingreso_text}

FECHA DE INGRESO: {fecha_ingreso}
FECHA DE EGRESO: {fecha_egreso}
EDAD: {edad} años
SEXO: {sexo}
DÍAS DE INTERNACIÓN: {dias_estada}

RESPONDE SOLO CON:
{{"evolucion": "..."}}
""",
    input_variables=[
        "evoluciones_text", "ingreso_text", "edad", "sexo", "dias_estada",
        "tipo_alta_oficial", "instruccion_obito", "fecha_ingreso", "fecha_egreso"
    ]
)


# =============================================================================
# SECCIÓN 3: PROCEDIMIENTOS
# =============================================================================

PROMPT_PROCEDIMIENTOS = PromptTemplate(
    template="""Extrae SOLO los procedimientos médicos relevantes para la epicrisis.

REGLAS OBLIGATORIAS:
1. Formato para cada procedimiento: "DD/MM/YYYY HH:MM - Descripción"
2. Ordenar cronológicamente (del más antiguo al más reciente)
3. EXCLUIR rutina de enfermería: signos vitales, higiene, control, baño, pañal, administración medicación
4. INCLUIR SOLO: cirugías, estudios de imagen, procedimientos invasivos, laboratorios importantes
5. Agrupar laboratorios repetitivos: "Laboratorios realizados (N estudios)"
6. Responder con lista JSON válida

CATEGORÍAS A INCLUIR:
✅ Quirúrgicos (cirugías, toilette, escarectomía)
✅ Estudios de imagen (RX, TAC, ECO, Doppler, Arteriografía)
✅ Procedimientos invasivos (IOT, ARM, vía central, sonda vesical, diálisis)
✅ Laboratorios (hemograma, bioquímica, hemocultivos, PCR específicos)
✅ Interconsultas de especialidades

CATEGORÍAS A EXCLUIR:
❌ Signos vitales, control de temperatura
❌ Higiene personal, baño de cama
❌ Cambio de pañal, ropa de cama
❌ Administración de medicación oral/EV
❌ Control de goteo, permeabilidad de vía
❌ Observación del paciente, sueño
❌ Valoraciones de enfermería rutinarias

CONTEXTO - PROCEDIMIENTOS:
{procedimientos_text}

RESPONDE SOLO CON:
{{"procedimientos": ["DD/MM/YYYY HH:MM - ...", "DD/MM/YYYY HH:MM - ..."]}}
""",
    input_variables=["procedimientos_text"]
)


# =============================================================================
# SECCIÓN 4: INTERCONSULTAS
# =============================================================================

PROMPT_INTERCONSULTAS = PromptTemplate(
    template="""Extrae las interconsultas a especialidades durante la internación.

REGLAS OBLIGATORIAS:
1. Formato: "DD/MM/YYYY (hora no registrada) - DD/MM/YYYY: Especialidad (N seguimientos)"
2. Si hay múltiples seguimientos de la misma especialidad, agrupar
3. Ordenar alfabéticamente por especialidad
4. Incluir resumen de 1-2 líneas del motivo/hallazgo principal
5. Formato de cada elemento: "Fecha - Especialidad: Resumen"
6. Responder con lista JSON válida

ESPECIALIDADES COMUNES:
- Clínica Médica
- Cirugía Vascular Periférica
- Cirugía Plástica
- Cirugía General
- Traumatología
- Nefrología
- Cardiología
- Infectología
- Kinesiología
- Nutrición
- Terapia Intensiva / UTI

CONTEXTO - INTERCONSULTAS:
{interconsultas_text}

RESPONDE SOLO CON:
{{"interconsultas": ["DD/MM/YYYY - Especialidad: ...", "DD/MM/YYYY - Especialidad: ..."]}}
""",
    input_variables=["interconsultas_text"]
)


# =============================================================================
# SECCIÓN 5: PLAN TERAPÉUTICO (MEDICACIÓN)
# =============================================================================

PROMPT_PLAN_TERAPEUTICO = PromptTemplate(
    template="""Extrae y clasifica la medicación en dos grupos:

1. **Medicación durante internación**: Fármacos indicados durante la hospitalización
2. **Medicación habitual previa**: Medicación crónica del paciente (de antecedentes)

REGLAS OBLIGATORIAS:
1. Ordenar alfabéticamente por fármaco en cada grupo
2. Formato para cada medicamento:
   - "farmaco": nombre del fármaco
   - "dosis": cantidad + unidad (ej: "100 mg")
   - "via": vía de administración ("Oral", "Intravenoso", "Subcutáneo", etc.)
   - "frecuencia": frecuencia de administración ("Cada 8 Hrs", "1 vez al día", etc.)
3. EXCLUIR soluciones de hidratación: SF, Ringer, Dextrosa, Glucosalina
4. Eliminar duplicados (mismo fármaco → mantener solo uno)
5. Capitalizar correctamente los nombres de fármacos
6. Responder con JSON válido

CONTEXTO - INDICACIONES FARMACOLÓGICAS:
{indicaciones_text}

CONTEXTO - ANTECEDENTES / MEDICACIÓN HABITUAL:
{antecedentes_text}

RESPONDE SOLO CON:
{{
  "medicacion_internacion": [
    {{"farmaco": "...", "dosis": "...", "via": "...", "frecuencia": "..."}},
    ...
  ],
  "medicacion_previa": [
    {{"farmaco": "...", "dosis": "...", "via": "...", "frecuencia": "..."}},
    ...
  ]
}}
""",
    input_variables=["indicaciones_text", "antecedentes_text"]
)


# =============================================================================
# HELPER: Prompt para diagnóstico CIE-10
# =============================================================================

PROMPT_DIAGNOSTICO_CIE10 = PromptTemplate(
    template="""Del siguiente texto de diagnósticos, extrae el diagnóstico principal con código CIE-10 si está disponible.

REGLAS:
1. Formato: "CÓDIGO - DESCRIPCIÓN" (ej: "I50.9 - INSUFICIENCIA CARDÍACA NO ESPECIFICADA")
2. Si no hay código CIE-10, responder con string vacío
3. Priorizar el diagnóstico marcado como "principal" o el primero de la lista

CONTEXTO - DIAGNÓSTICOS:
{diagnosticos_text}

RESPONDE SOLO CON:
{{"diagnostico_principal_cie10": "..."}}
""",
    input_variables=["diagnosticos_text"]
)
