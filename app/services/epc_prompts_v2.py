# app/services/epc_prompts_v2.py
"""
EPC Prompts V2 - Prompts especializados y condicionales.

Estrategia:
- PROMPT_MOTIVO_REAL: Extrae motivo de ingreso desde Triage/Admisión.
- PROMPT_EVOLUCION_*: Resumen narrativo basado en historia completa.
- PROMPT_PROCEDIMIENTOS: Filtrado inteligente y agrupamiento.
- PROMPT_PLAN_TERAPEUTICO: División estricta internación vs previa.
"""

from langchain_core.prompts import PromptTemplate

# =============================================================================
# 1. MOTIVO DE INTERNACIÓN (REAL)
# =============================================================================
PROMPT_MOTIVO_REAL = PromptTemplate(
    template="""Identifica el MOTIVO REAL de internación del paciente.

FUENTE DE VERDAD:
1. Lo que el paciente declaró en admisión/triage.
2. El diagnóstico de ingreso o presuntivo inicial.
3. NO confundir con antecedentes o diagnósticos secundarios.

CONTEXTO INICIAL (Triage/Admisión/Primeras evoluciones):
{motivo_text}

INSTRUCCIONES:
- Sé conciso (máximo 1-2 líneas).
- Ej: "Dolor abdominal en fosa ilíaca derecha." o "Disnea progresiva CF III-IV."

RESPONDE SOLO CON JSON:
{{"motivo_internacion": "..."}}
""",
    input_variables=["motivo_text"]
)

# =============================================================================
# 2. EVOLUCIÓN (ESTÁNDAR)
# =============================================================================
PROMPT_EVOLUCION_ESTANDAR = PromptTemplate(
    template="""Genera la sección EVOLUCIÓN de la epicrisis (Resumen 100% Completo).

REGLAS:
1. Iniciar: "Paciente de {edad} años, sexo {sexo}, ..."
2. Narrativa cronológica COMPLETA: ingreso → evaluación → complicaciones → tratamiento → respuesta → egreso.
3. BASARSE EN TODA LA HISTORIA CLÍNICA provista. No omitir eventos importantes.
4. Si hay interconsultas relevantes, mencionarlas brevemente en el flujo narrativo.
5. NO listar fármacos con dosis (eso va en Plan Terapéutico). Mencionar grupos ("se inició antibióticos", "se rotó a vía oral").

CONTEXTO (Historia Clínica Completa):
{historia_completa}

DATOS:
Edad: {edad}
Sexo: {sexo}
Días estada: {dias_estada}
Egreso: {fecha_egreso}

RESPONDE SOLO CON JSON:
{{"evolucion": "..."}}
""",
    input_variables=["historia_completa", "edad", "sexo", "dias_estada", "fecha_egreso"]
)

# =============================================================================
# 3. EVOLUCIÓN (ÓBITO) - CON NARRATIVA CLÍNICA COMPLETA
# =============================================================================
PROMPT_EVOLUCION_OBITO = PromptTemplate(
    template="""Genera la sección EVOLUCIÓN de la epicrisis para un paciente FALLECIDO.

⚠️ IMPORTANTE: DEBES GENERAR UNA EVOLUCIÓN CLÍNICA COMPLETA (2-4 párrafos) Y SOLO AL FINAL EL BLOQUE DE ÓBITO.

ESTRUCTURA OBLIGATORIA:
1. PRIMER PÁRRAFO: "Paciente de {edad} años, sexo {sexo}, con antecedentes de... que ingresa por..."
2. PÁRRAFOS INTERMEDIOS: Describe cronológicamente:
   - Evaluación inicial y hallazgos
   - Estudios realizados y resultados relevantes
   - Tratamientos instaurados
   - Evolución durante la internación (mejoría inicial si la hubo, complicaciones)
   - Deterioro clínico que llevó al fallecimiento
3. ÚLTIMO PÁRRAFO (OBLIGATORIO): "PACIENTE OBITÓ - Fecha: {fecha_egreso} Hora: {hora_egreso}. Se constata óbito."

⛔ REGLAS CRÍTICAS DE ÓBITO:
- EL PACIENTE FALLECIÓ. Es IMPOSIBLE que "se vaya de alta", "se retire", "mejore" o tenga "controles ambulatorios".
- ELIMINA referencias a "alta a domicilio", "buena evolución", "mejoría al alta". SON FALSAS.
- NO OMITAS la narrativa clínica. El bloque de óbito es SOLO el párrafo final.
- NO generes solo el bloque de óbito sin la evolución clínica completa.

EJEMPLO DE RESPUESTA CORRECTA:
"Paciente de 83 años, sexo masculino, con antecedentes de DBT II, HTA, que ingresa por síndrome febril y alteración del sensorio.

Al ingreso se constata foco neumónico basal bilateral. Se inicia tratamiento antibiótico empírico. Evoluciona con deterioro progresivo de la función renal y compromiso hemodinámico, requiriendo expansión con cristaloides.

Pese al tratamiento instaurado, el paciente evoluciona desfavorablemente con falla multiorgánica.

PACIENTE OBITÓ - Fecha: 27/02/2023 Hora: 07:02. Se constata óbito."

CONTEXTO (Historia Clínica Completa):
{historia_completa}

DATOS:
Edad: {edad}
Sexo: {sexo}
Días estada: {dias_estada}
Egreso: {fecha_egreso}

RESPONDE SOLO CON JSON:
{{"evolucion": "..."}}
""",
    input_variables=["historia_completa", "edad", "sexo", "dias_estada", "fecha_egreso", "hora_egreso"]
)

# =============================================================================
# 4. PROCEDIMIENTOS (LISTA INTELIGENTE)
# =============================================================================
PROMPT_PROCEDIMIENTOS = PromptTemplate(
    template="""Genera la lista de PROCEDIMIENTOS realizados.

ENTRADA:
{procedimientos_list}

REGLAS DE FILTRADO:
1. ELIMINAR rutinas de enfermería irrelevantes: "Higienes", "Control signos vitales", "Cambio de pañal", "Curación plana" (salvo que sea cirugía).
2. MANTENER: Cirugías, Accesos venosos centrales, Intubación, Sondajes, Transfusiones, Estudios de imagen (Rx, TC, Eco), Biopsias.
3. SINTETIZAR: Si hay múltiples "Curaciones", poner solo una vez "Curaciones de herida quirúrgica".

FORMATO DE SALIDA (Lista de Strings):
- "- [Fecha] Procedimiento"
- IMPORTANTE: No incluyas laboratorios aquí (se manejan aparte).

RESPONDE SOLO CON JSON:
{{"procedimientos": ["- [DD/MM] Procedimiento 1", "- [DD/MM] Procedimiento 2"]}}
""",
    input_variables=["procedimientos_list"]
)

# =============================================================================
# 5. PLAN TERAPÉUTICO (DIVIDIDO)
# =============================================================================
PROMPT_PLAN_TERAPEUTICO = PromptTemplate(
    template="""Identifica y separa la medicación en DOS grupos.

1. MEDICACIÓN DE INTERNACIÓN: Fármacos administrados DURANTE la hospitalización (ATB, analgesia rescate, etc).
2. MEDICACIÓN PREVIA (HABITUAL): Fármacos que el paciente TOMABA ANTES de ingresar (antecedentes).

FUENTES:
- Indicaciones: {indicaciones_text}
- Antecedentes/Ingreso: {antecedentes_text}

RESPONDE SOLO CON JSON:
{{
  "medicacion_internacion": [
    {{"farmaco": "Nombre", "dosis": "...", "via": "...", "frecuencia": "..."}}
  ],
  "medicacion_previa": [
    {{"farmaco": "Nombre", "dosis": "...", "observacion": "..."}}
  ]
}}
""",
    input_variables=["indicaciones_text", "antecedentes_text"]
)

# =============================================================================
# 6. INTERCONSULTAS
# =============================================================================
PROMPT_INTERCONSULTAS = PromptTemplate(
    template="""Resumen de INTERCONSULTAS realizadas.

ENTRADA:
{interconsultas_text}

REGLAS:
1. Agrupar por especialidad si hay varias visitas de la misma (ej: "Cardiología (3 visitas)").
2. Resumir la conclusión o conducta principal.
3. NO repetir contenido.

RESPONDE SOLO CON JSON:
{{"interconsultas": ["- [DD/MM] Especialidad: Resumen breve"]}}
""",
    input_variables=["interconsultas_text"]
)
