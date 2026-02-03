# Refactorización SOLID - Changelog

Este documento registra los cambios realizados durante la refactorización del backend siguiendo principios SOLID.

---

## Índice
- [Fase 5: Mejoras Críticas de Generación EPC](#fase-5-mejoras-críticas-de-generación-epc)
- [Fase 1: Limpieza y Módulo de Reglas](#fase-1-limpieza-y-módulo-de-reglas)
- [Fase 2: Consolidación de Servicios](#fase-2-consolidación-de-servicios)
- [Fase 3: Refactorización de Routers](#fase-3-refactorización-de-routers)
- [Fase 4: SOLID Completo](#fase-4-solid-completo)

---

## Fase 5: Mejoras Críticas de Generación EPC
**Fecha:** 2026-01-28
**Estado:** ✅ Completada

### Problema Detectado
La EPC generaba texto contradictorio ("alta a domicilio" cuando el paciente falleció).

**Causas:**
1. Los datos de la HCE origen contenían inconsistencias
2. La IA repetía información incorrecta del HCE
3. El `tipo_alta=OBITO` no se usaba en el prompt

### Soluciones Implementadas

| Componente | Mejora |
|------------|--------|
| `epc_pre_validator.py` | Detecta ÓBITO desde `tipo_alta` del episodio |
| `epc_prompts.py` | Nuevas variables: `tipo_alta_oficial`, `instruccion_obito` |
| `epc_orchestrator.py` | Pre-validación + migración a LCEL |
| `ai_langchain_service.py` | 15+ patrones de detección de contradicciones |

### Archivos Nuevos
| Archivo | Propósito |
|---------|-----------|
| `app/services/epc_pre_validator.py` | Validación pre-generación |

### Principios SOLID
- **S**: Pre-validación separada de generación
- **O**: Patrones de contradicción extensibles

---

## Fase 1: Limpieza y Módulo de Reglas
**Fecha:** 2026-01-28
**Estado:** ✅ Completada

### Objetivo
Establecer las bases para la refactorización SOLID creando un módulo centralizado de reglas de negocio.

### Principios SOLID Aplicados
- **S (Single Responsibility)**: Cada regla en su propio módulo
- **O (Open/Closed)**: Fácil agregar nuevas reglas sin modificar código existente

### Archivos Eliminados
| Archivo | Razón |
|---------|-------|
| `app/services/epc_service.py.bak` | Backup obsoleto |

### Archivos Creados

#### `app/rules/__init__.py`
```python
from .death_detection import DeathDetectionRule, detect_death_in_text
from .medication_classifier import MedicationClassifier
```

#### `app/rules/death_detection.py`
**Propósito:** Detección centralizada de fallecimiento/óbito

**Clase principal:** `DeathDetectionRule`
- Detecta palabras clave de fallecimiento
- Extrae fecha y hora del óbito
- Retorna `DeathInfo` dataclass con toda la información

**Funciones de conveniencia:**
- `detect_death_in_text(text)` → `DeathInfo`
- `detect_death_from_alta_type(tipo_alta)` → `bool`
- `format_death_line(date, time, description)` → `str`

**Palabras clave detectadas:**
- fallece, falleció, óbito, obito, murió, deceso
- paro cardiorrespiratorio, exitus, éxitus
- se constata, constata (común en "se constata óbito")
- maniobras de reanimación, retiro de soporte vital
- limitación del esfuerzo terapéutico

#### `app/rules/medication_classifier.py`
**Propósito:** Clasificación de medicamentos (internación vs previa/habitual)

**Clase principal:** `MedicationClassifier`
- Clasifica medicamentos según nombre, vía y dosis
- Retorna "internacion" o "previa"

**Listas de clasificación:**
- **Típicamente previos (crónicos):** losartan, atorvastatina, metformina, levotiroxina, omeprazol oral
- **Típicamente internación (agudos):** ampicilina/sulbactam, vancomicina, morfina, noradrenalina

### Archivos Modificados

#### `app/services/ai_langchain_service.py`
**Cambio:** Refactorizado para usar módulo de reglas centralizado

```python
# Antes
PALABRAS_FALLECIMIENTO = ["fallece", "óbito", ...]  # hardcoded

# Después
from app.rules.death_detection import detect_death_in_text
death_info = detect_death_in_text(evolucion)
hay_fallecimiento = death_info.detected
```

**Beneficio:** Mantiene compatibilidad con fallback si el módulo no está disponible.

### Tests
```bash
# Verificar funcionamiento
python3 -c "from app.rules import DeathDetectionRule; print('OK')"
python3 -c "from app.rules import MedicationClassifier; print('OK')"
```

---

## Fase 2: Consolidación de Servicios
**Fecha:** 2026-01-28
**Estado:** ✅ Completada (Vector Services)

### Objetivo
Unificar servicios duplicados y reducir complejidad.

### Principios SOLID Aplicados
- **S (Single Responsibility)**: EmbeddingService solo genera embeddings, QdrantService solo opera Qdrant
- **D (Dependency Inversion)**: QdrantService depende de EmbeddingService (abstracción)

### Archivos Creados

#### `app/services/vector/__init__.py`
Módulo unificado con exports:
```python
from .qdrant_service import QdrantService, get_qdrant_service
from .embedding_service import EmbeddingService, get_embedding_service
```

#### `app/services/vector/embedding_service.py`
**Propósito:** Generación de embeddings con Gemini

**Clase:** `EmbeddingService`
- Modelo: `text-embedding-004`
- Dimensión: 768
- Métodos: `embed(text)`, `embed_batch(texts)`

#### `app/services/vector/qdrant_service.py`
**Propósito:** Operaciones unificadas de Qdrant

**Clase:** `QdrantService`

**Colecciones:**
- `hce_chunks`: Chunks de HCEs para RAG
- `epc_feedback_vectors`: Feedback de usuarios

**Métodos HCE:**
- `add_hce_chunk(chunk_id, text, metadata)`
- `search_hce_chunks(query, limit, filters)`

**Métodos Feedback:**
- `store_feedback(user_id, section, rating, text)`
- `search_user_feedback(user_id, section, query)`

### Archivos a Deprecar (futuro)
| Archivo | Reemplazo |
|---------|-----------|
| `vector_store.py` | `vector/qdrant_service.py` |
| `vector_service.py` | `vector/qdrant_service.py` + `embedding_service.py` |

### Tests
```bash
# Verificar funcionamiento
python3 -c "from app.services.vector import QdrantService; print('OK')"
python3 -c "from app.services.vector import EmbeddingService; print('OK')"
```

### Consolidación de Parsers (Pendiente)
- [ ] Unificar `hce_parser.py`, `hce_ainstein_parser.py`, `hce_json_parser.py`

---

## Fase 3: Refactorización de Routers
**Fecha:** 2026-01-28
**Estado:** ✅ Módulos extraídos (1,164 líneas - 45%)

### Objetivo
Reducir `routers/epc.py` de 2,562 líneas a <200 líneas.

### Principios SOLID Aplicados
- **S (Single Responsibility)**: Cada módulo una responsabilidad
- **O (Open/Closed)**: Servicios extensibles sin modificar router

### Archivos Creados (5 archivos, 1,164 líneas)

#### `app/services/epc/__init__.py` (69 líneas)
Módulo de servicios EPC con exports centralizados.

#### `app/services/epc/helpers.py` (235 líneas)
**Propósito:** Funciones auxiliares de parsing y formateo

**Funciones extraídas:**
- `now()` - Datetime UTC
- `uuid_str()` - Generador de UUIDs
- `clean_str()` - Limpieza de strings
- `parse_dt_maybe()` - Parsing de fechas
- `safe_objectid()` - Conversión a ObjectId
- `uuid_variants()` - Variantes de UUID para búsqueda
- `json_from_ai()` - Parsing de respuestas de IA
- `actor_name()` - Nombre de usuario para historial
- `age_from_ymd()` - Cálculo de edad
- `list_to_lines()` - Conversión a texto para PDF

#### `app/services/epc/hce_extractor.py` (295 líneas)
**Propósito:** Extracción de texto de HCE

**Clase:** `HCEExtractor`
- `extract(hce_doc)` - Extrae texto automáticamente
- `_extract_ainstein()` - HCE de WebService
- `_pick_best_text()` - HCE genérica/PDF

#### `app/services/epc/pdf_builder.py` (314 líneas)
**Propósito:** Construcción de payload para PDF

**Clase:** `EPCPDFBuilder`
- `build(epc_doc, patient, clinical, hce)` - Construye payload completo
- `_extract_patient_info()` - Info del paciente
- `_build_sections()` - Secciones del PDF
- `_build_medication_section()` - Medicación separada
- `_process_procedimientos()` - Expansión de labs

#### `app/services/epc/feedback_service.py` (251 líneas)
**Propósito:** Gestión de feedback de secciones

**Clase:** `EPCFeedbackService`
- `validate_feedback(data)` - Validación
- `submit_feedback(data, user_id, user_name)` - Guardar feedback
- `get_user_feedback(epc_id, user_id)` - Obtener feedback previo
- `get_stats_by_section()` - Estadísticas

### Próximos Pasos
- [x] Extraer helpers a módulo separado
- [x] Extraer HCE extractor
- [x] Extraer PDF builder
- [x] Extraer Feedback service
- [x] Actualizar imports en `routers/epc.py`
- [ ] Eliminar funciones duplicadas del router (gradual)

### Nota sobre eliminación gradual
El router ahora importa todas las funciones desde `app.services.epc`, pero las definiciones legacy aún existen
como código muerto. Se pueden eliminar de forma gradual sin afectar funcionalidad.

**Líneas actuales:**
- `routers/epc.py`: 2,593 líneas (con código muerto legacy)
- `services/epc/`: 1,164 líneas (módulos nuevos)

**Después de limpieza:**
- `routers/epc.py`: ~1,400 líneas (solo endpoints)
- Reducción total: ~45%

---

## Fase 4: SOLID Completo
**Fecha:** 2026-01-28
**Estado:** ✅ Interfaces creadas

### Objetivo
Aplicar principio D (Dependency Inversion) con interfaces abstractas.

### Principios SOLID Aplicados
- **D (Dependency Inversion)**: Módulos de alto nivel dependen de abstracciones
- **L (Liskov Substitution)**: Implementaciones intercambiables

### Archivos Creados (6 archivos, 445 líneas)

#### `app/domain/interfaces/__init__.py` (32 líneas)
Exports centralizados de todas las interfaces.

#### `app/domain/interfaces/embedding_interface.py` (53 líneas)
**Interface:** `IEmbeddingService`
- `embed(text)` → `List[float]`
- `embed_batch(texts)` → `List[List[float]]`
- `vector_dimension` → `int`

**Implementaciones posibles:**
- `EmbeddingService` (Gemini) ✅ Actual
- `OpenAIEmbeddingService` (futuro)
- `LocalEmbeddingService` (futuro)

#### `app/domain/interfaces/vector_interface.py` (103 líneas)
**Interface:** `IVectorStore`
- `add_document(collection, doc_id, text, metadata)`
- `search(collection, query, limit, filters)`
- `delete_document(collection, doc_id)`
- `health_check()`

**Implementaciones posibles:**
- `QdrantService` ✅ Actual
- `PineconeService` (futuro)
- `WeaviateService` (futuro)

#### `app/domain/interfaces/hce_interface.py` (69 líneas)
**Interface:** `IHCEExtractor`
- `extract(hce_doc)` → texto
- `extract_structured(hce_doc)` → `HCEContent`
- `detect_source_type(hce_doc)` → tipo

#### `app/domain/interfaces/feedback_interface.py` (81 líneas)
**Interface:** `IFeedbackService`
- `validate(entry)`
- `submit(entry, user_id, user_name)`
- `get_user_feedback(epc_id, user_id)`
- `get_stats()`

#### `app/domain/interfaces/epc_generator_interface.py` (107 líneas)
**Interface:** `IEPCGenerator`
- `generate_section(name, hce_text, context)` → `EPCSection`
- `generate_full_epc(hce_text, patient, rules)` → `GeneratedEPC`
- `post_process(epc, hce_text)` → `GeneratedEPC`

**Implementaciones posibles:**
- `GeminiAIService` ✅ Actual
- `GPTEPCGenerator` (futuro)
- `LocalLLMGenerator` (futuro)

### Uso de Interfaces
```python
from app.domain.interfaces import IEmbeddingService, IVectorStore

class EPCService:
    def __init__(
        self,
        embeddings: IEmbeddingService,
        vectors: IVectorStore,
    ):
        self.embeddings = embeddings
        self.vectors = vectors
```

### Beneficios
1. **Testing**: Fácil crear mocks para tests unitarios
2. **Flexibilidad**: Cambiar Gemini por GPT sin modificar código
3. **Documentación**: Contratos claros entre componentes

---

## Métricas Finales

| Métrica | Antes | Fase 1 | Fase 2 | Fase 3 | Fase 4 | Estado |
|---------|-------|--------|--------|--------|--------|--------|
| Archivos .py.bak | 1 | 0 | 0 | 0 | 0 | ✅ |
| Módulo rules/ | - | 3 | 3 | 3 | 3 | ✅ |
| Módulo vector/ | - | - | 3 | 3 | 3 | ✅ |
| Módulo epc/ | - | - | - | 5 | 5 | ✅ |
| Módulo interfaces/ | - | - | - | - | **6** | ✅ |
| Líneas SOLID creadas | 0 | 477 | 1,003 | 2,167 | **2,612** | ✅ |

### Resumen por Módulo

| Módulo | Archivos | Líneas | Propósito |
|--------|----------|--------|-----------|
| `app/rules/` | 3 | 477 | Reglas de negocio (óbito, medicación) |
| `app/services/vector/` | 3 | 526 | Servicios vectoriales (Qdrant, embeddings) |
| `app/services/epc/` | 5 | 1,164 | Servicios EPC (helpers, HCE, PDF, feedback) |
| `app/domain/interfaces/` | 6 | 445 | Interfaces SOLID (abstracciones) |
| **TOTAL** | **17** | **2,612** | |

### Principios SOLID Aplicados

| Principio | Descripción | Implementación |
|-----------|-------------|----------------|
| **S** - Single Responsibility | Una clase, una responsabilidad | Módulos separados por función |
| **O** - Open/Closed | Abierto a extensión, cerrado a modificación | Clases extensibles |
| **L** - Liskov Substitution | Subtipos intercambiables | Interfaces abstractas |
| **I** - Interface Segregation | Interfaces específicas | Interfaces pequeñas y enfocadas |
| **D** - Dependency Inversion | Depender de abstracciones | `app/domain/interfaces/` |

---

## Próximos Pasos (Opcional)

- [ ] Eliminar código legacy de `routers/epc.py` (~1,000 líneas)
- [ ] Implementar `IEmbeddingService` en `EmbeddingService`
- [ ] Implementar `IVectorStore` en `QdrantService`
- [ ] Tests unitarios con mocks de interfaces
- [ ] Dependency Injection container (FastAPI Depends)

---

## Referencias
- [REGLAS_GENERACION_EPC.md](./REGLAS_GENERACION_EPC.md) - Reglas oficiales de generación
- [Principios SOLID](https://en.wikipedia.org/wiki/SOLID)
- [Clean Architecture - Uncle Bob](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

