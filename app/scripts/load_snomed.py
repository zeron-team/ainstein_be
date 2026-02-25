#!/usr/bin/env python3
"""
Complete SNOMED CT Argentina Extension → PostgreSQL Loader.
Imports 100% of all Snapshot + Resources TXT files.
Usage: cd backend && .venv/bin/python3 app/scripts/load_snomed.py
"""
import os, sys, time, csv, io, glob
import psycopg2

DSN = "host=localhost port=5432 dbname=ainstein user=ainstein password=ainstein_secure_2026"

SNOMED_ROOT = os.path.join(
    os.path.dirname(__file__), "..", "..", "docs",
    "SnomedCT_Argentina-ExtensionRelease_PRODUCTION_20251120T120000Z",
)
SNAPSHOT = os.path.join(SNOMED_ROOT, "Snapshot")
RESOURCES = os.path.join(SNOMED_ROOT, "Resources")
TERM_DIR = os.path.join(SNAPSHOT, "Terminology")


DDL = """
-- =============================================
-- CORE TERMINOLOGY TABLES
-- =============================================
DROP TABLE IF EXISTS snomed_refset_member CASCADE;
DROP TABLE IF EXISTS snomed_map_icd10 CASCADE;
DROP TABLE IF EXISTS snomed_map_simple CASCADE;
DROP TABLE IF EXISTS snomed_language CASCADE;
DROP TABLE IF EXISTS snomed_concrete_value CASCADE;
DROP TABLE IF EXISTS snomed_stated_relationship CASCADE;
DROP TABLE IF EXISTS snomed_relationship CASCADE;
DROP TABLE IF EXISTS snomed_text_definition CASCADE;
DROP TABLE IF EXISTS snomed_description CASCADE;
DROP TABLE IF EXISTS snomed_owl_expression CASCADE;
DROP TABLE IF EXISTS snomed_identifier CASCADE;
DROP TABLE IF EXISTS snomed_concept CASCADE;
DROP TABLE IF EXISTS snomed_refset CASCADE;
DROP TABLE IF EXISTS snomed_association CASCADE;
DROP TABLE IF EXISTS snomed_attribute_value CASCADE;
DROP TABLE IF EXISTS snomed_medicinal_product CASCADE;

-- 1. Concepts
CREATE TABLE snomed_concept (
    id                    BIGINT PRIMARY KEY,
    effective_time        VARCHAR(8),
    active                BOOLEAN NOT NULL,
    module_id             BIGINT NOT NULL,
    definition_status_id  BIGINT NOT NULL
);

-- 2. Descriptions (terms in Spanish)
CREATE TABLE snomed_description (
    id                    BIGINT PRIMARY KEY,
    effective_time        VARCHAR(8),
    active                BOOLEAN NOT NULL,
    module_id             BIGINT NOT NULL,
    concept_id            BIGINT NOT NULL,
    language_code         VARCHAR(5) NOT NULL,
    type_id               BIGINT NOT NULL,
    term                  TEXT NOT NULL,
    case_significance_id  BIGINT NOT NULL
);

-- 3. Relationships (hierarchical)
CREATE TABLE snomed_relationship (
    id                        BIGINT PRIMARY KEY,
    effective_time            VARCHAR(8),
    active                    BOOLEAN NOT NULL,
    module_id                 BIGINT NOT NULL,
    source_id                 BIGINT NOT NULL,
    destination_id            BIGINT NOT NULL,
    relationship_group        INTEGER NOT NULL,
    type_id                   BIGINT NOT NULL,
    characteristic_type_id    BIGINT NOT NULL,
    modifier_id               BIGINT NOT NULL
);

-- 4. Stated Relationships
CREATE TABLE snomed_stated_relationship (
    id                        BIGINT PRIMARY KEY,
    effective_time            VARCHAR(8),
    active                    BOOLEAN NOT NULL,
    module_id                 BIGINT NOT NULL,
    source_id                 BIGINT NOT NULL,
    destination_id            BIGINT NOT NULL,
    relationship_group        INTEGER NOT NULL,
    type_id                   BIGINT NOT NULL,
    characteristic_type_id    BIGINT NOT NULL,
    modifier_id               BIGINT NOT NULL
);

-- 5. Concrete Values
CREATE TABLE snomed_concrete_value (
    id                        BIGINT PRIMARY KEY,
    effective_time            VARCHAR(8),
    active                    BOOLEAN NOT NULL,
    module_id                 BIGINT NOT NULL,
    source_id                 BIGINT NOT NULL,
    value                     TEXT NOT NULL,
    relationship_group        INTEGER NOT NULL,
    type_id                   BIGINT NOT NULL,
    characteristic_type_id    BIGINT NOT NULL,
    modifier_id               BIGINT NOT NULL
);

-- 6. Text Definitions
CREATE TABLE snomed_text_definition (
    id                    BIGINT PRIMARY KEY,
    effective_time        VARCHAR(8),
    active                BOOLEAN NOT NULL,
    module_id             BIGINT NOT NULL,
    concept_id            BIGINT NOT NULL,
    language_code         VARCHAR(5) NOT NULL,
    type_id               BIGINT NOT NULL,
    term                  TEXT NOT NULL,
    case_significance_id  BIGINT NOT NULL
);

-- 7. OWL Expressions
CREATE TABLE snomed_owl_expression (
    id                    TEXT PRIMARY KEY,
    effective_time        VARCHAR(8),
    active                BOOLEAN NOT NULL,
    module_id             BIGINT NOT NULL,
    refset_id             BIGINT NOT NULL,
    referenced_component_id BIGINT NOT NULL,
    owl_expression        TEXT NOT NULL
);

-- 8. Language Refset
CREATE TABLE snomed_language (
    id                    TEXT PRIMARY KEY,
    effective_time        VARCHAR(8),
    active                BOOLEAN NOT NULL,
    module_id             BIGINT NOT NULL,
    refset_id             BIGINT NOT NULL,
    referenced_component_id BIGINT NOT NULL,
    acceptability_id      BIGINT NOT NULL
);

-- 9. Extended Map (SNOMED → ICD-10)
CREATE TABLE snomed_map_icd10 (
    id                    TEXT PRIMARY KEY,
    effective_time        VARCHAR(8),
    active                BOOLEAN NOT NULL,
    module_id             BIGINT NOT NULL,
    refset_id             BIGINT NOT NULL,
    referenced_component_id BIGINT NOT NULL,
    map_group             INTEGER,
    map_priority          INTEGER,
    map_rule              TEXT,
    map_advice            TEXT,
    map_target            VARCHAR(20),
    correlation_id        BIGINT,
    map_category_id       BIGINT
);

-- 10. Simple Map
CREATE TABLE snomed_map_simple (
    id                    TEXT PRIMARY KEY,
    effective_time        VARCHAR(8),
    active                BOOLEAN NOT NULL,
    module_id             BIGINT NOT NULL,
    refset_id             BIGINT NOT NULL,
    referenced_component_id BIGINT NOT NULL,
    map_target            TEXT
);

-- 11. Association Refset
CREATE TABLE snomed_association (
    id                    TEXT PRIMARY KEY,
    effective_time        VARCHAR(8),
    active                BOOLEAN NOT NULL,
    module_id             BIGINT NOT NULL,
    refset_id             BIGINT NOT NULL,
    referenced_component_id BIGINT NOT NULL,
    target_component_id   BIGINT NOT NULL
);

-- 12. Attribute Value Refset
CREATE TABLE snomed_attribute_value (
    id                    TEXT PRIMARY KEY,
    effective_time        VARCHAR(8),
    active                BOOLEAN NOT NULL,
    module_id             BIGINT NOT NULL,
    refset_id             BIGINT NOT NULL,
    referenced_component_id BIGINT NOT NULL,
    value_id              BIGINT NOT NULL
);

-- 13. Simple Refset (content)
CREATE TABLE snomed_refset (
    id                    TEXT PRIMARY KEY,
    effective_time        VARCHAR(8),
    active                BOOLEAN NOT NULL,
    module_id             BIGINT NOT NULL,
    refset_id             BIGINT NOT NULL,
    referenced_component_id BIGINT NOT NULL
);

-- 14. Medicinal Products Refset (6 component columns)
CREATE TABLE snomed_medicinal_product (
    id                    TEXT PRIMARY KEY,
    effective_time        VARCHAR(8),
    active                BOOLEAN NOT NULL,
    module_id             BIGINT NOT NULL,
    refset_id             BIGINT NOT NULL,
    referenced_component_id BIGINT NOT NULL,
    component1_id         BIGINT,
    component2_id         BIGINT,
    component3_id         BIGINT,
    component4_id         BIGINT,
    component5_id         BIGINT,
    component6_id         BIGINT
);

-- 15. Resources: Simple Refsets with term columns
CREATE TABLE snomed_resource_refset (
    id                    TEXT,
    effective_time        VARCHAR(8),
    active                BOOLEAN NOT NULL,
    module_id             BIGINT NOT NULL,
    refset_id             BIGINT NOT NULL,
    refset_name           TEXT,
    referenced_component_id BIGINT NOT NULL,
    referenced_component_term TEXT,
    source_file           TEXT
);

CREATE EXTENSION IF NOT EXISTS pg_trgm;
"""

INDEXES = """
CREATE INDEX ix_sn_desc_concept ON snomed_description(concept_id);
CREATE INDEX ix_sn_desc_term_trgm ON snomed_description USING gin(term gin_trgm_ops);
CREATE INDEX ix_sn_desc_active ON snomed_description(active) WHERE active = true;
CREATE INDEX ix_sn_desc_lang ON snomed_description(language_code);
CREATE INDEX ix_sn_desc_type ON snomed_description(type_id);
CREATE INDEX ix_sn_rel_source ON snomed_relationship(source_id);
CREATE INDEX ix_sn_rel_dest ON snomed_relationship(destination_id);
CREATE INDEX ix_sn_rel_type ON snomed_relationship(type_id);
CREATE INDEX ix_sn_rel_active ON snomed_relationship(active) WHERE active = true;
CREATE INDEX ix_sn_srel_source ON snomed_stated_relationship(source_id);
CREATE INDEX ix_sn_srel_dest ON snomed_stated_relationship(destination_id);
CREATE INDEX ix_sn_cv_source ON snomed_concrete_value(source_id);
CREATE INDEX ix_sn_lang_ref ON snomed_language(referenced_component_id);
CREATE INDEX ix_sn_map_concept ON snomed_map_icd10(referenced_component_id);
CREATE INDEX ix_sn_map_target ON snomed_map_icd10(map_target);
CREATE INDEX ix_sn_assoc_ref ON snomed_association(referenced_component_id);
CREATE INDEX ix_sn_assoc_target ON snomed_association(target_component_id);
CREATE INDEX ix_sn_refset_refsetid ON snomed_refset(refset_id);
CREATE INDEX ix_sn_refset_ref ON snomed_refset(referenced_component_id);
CREATE INDEX ix_sn_medprod_ref ON snomed_medicinal_product(referenced_component_id);
CREATE INDEX ix_sn_resref_refsetid ON snomed_resource_refset(refset_id);
CREATE INDEX ix_sn_resref_ref ON snomed_resource_refset(referenced_component_id);
CREATE INDEX ix_sn_resref_term ON snomed_resource_refset USING gin(referenced_component_term gin_trgm_ops);
"""


def copy_bulk(cur, conn, table, cols, filepath, transform_fn, label=""):
    """Fast bulk load via COPY."""
    buf = io.StringIO()
    count = 0
    skipped = 0
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        next(reader)
        for row in reader:
            try:
                vals = transform_fn(row)
                line = '\t'.join(str(v) for v in vals)
                buf.write(line + '\n')
                count += 1
            except Exception:
                skipped += 1
    buf.seek(0)
    try:
        cur.copy_expert(
            f"COPY {table} ({','.join(cols)}) FROM STDIN WITH (FORMAT text, DELIMITER E'\\t', NULL '\\\\N')",
            buf
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"    ⚠️ Error in COPY: {e}")
        return 0
    if label:
        extra = f" (skipped {skipped})" if skipped else ""
        print(f"    ✅ {count:,} {label}{extra}")
    return count


def bool_val(s):
    return 't' if s == '1' else 'f'

def safe(s):
    """Escape tabs/newlines for COPY."""
    return s.replace('\t', ' ').replace('\n', ' ').replace('\r', '') if s else '\\N'

def safe_bigint(s):
    return s if s and s.strip() else '\\N'


def main():
    print("=" * 60)
    print("SNOMED CT Argentina → PostgreSQL (COMPLETE)")
    print("=" * 60)

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    conn.autocommit = True
    cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    conn.autocommit = False

    # 1. CREATE TABLES
    print("\n1. Creating tables...")
    cur.execute(DDL)
    conn.commit()
    print("   ✅ All tables created")

    t0 = time.time()
    totals = {}

    # =====================================================
    # SNAPSHOT / TERMINOLOGY
    # =====================================================
    print("\n2. Loading Snapshot/Terminology...")

    # Concepts
    n = copy_bulk(cur, conn, "snomed_concept",
        ["id","effective_time","active","module_id","definition_status_id"],
        f"{TERM_DIR}/sct2_Concept_Snapshot_ArgentinaExtension_20251120.txt",
        lambda r: [r[0], r[1], bool_val(r[2]), r[3], r[4]],
        "concepts")
    totals["snomed_concept"] = n

    # Descriptions
    n = copy_bulk(cur, conn, "snomed_description",
        ["id","effective_time","active","module_id","concept_id","language_code","type_id","term","case_significance_id"],
        f"{TERM_DIR}/sct2_Description_Snapshot_ArgentinaExtension_20251120.txt",
        lambda r: [r[0], r[1], bool_val(r[2]), r[3], r[4], r[5], r[6], safe(r[7]), r[8]],
        "descriptions")
    totals["snomed_description"] = n

    # Relationships
    n = copy_bulk(cur, conn, "snomed_relationship",
        ["id","effective_time","active","module_id","source_id","destination_id","relationship_group","type_id","characteristic_type_id","modifier_id"],
        f"{TERM_DIR}/sct2_Relationship_Snapshot_ArgentinaExtension_20251120.txt",
        lambda r: [r[0], r[1], bool_val(r[2]), r[3], r[4], r[5], r[6], r[7], r[8], r[9]],
        "relationships")
    totals["snomed_relationship"] = n

    # Stated Relationships
    n = copy_bulk(cur, conn, "snomed_stated_relationship",
        ["id","effective_time","active","module_id","source_id","destination_id","relationship_group","type_id","characteristic_type_id","modifier_id"],
        f"{TERM_DIR}/sct2_StatedRelationship_Snapshot_ArgentinaExtension_20251120.txt",
        lambda r: [r[0], r[1], bool_val(r[2]), r[3], r[4], r[5], r[6], r[7], r[8], r[9]],
        "stated relationships")
    totals["snomed_stated_relationship"] = n

    # Concrete Values
    n = copy_bulk(cur, conn, "snomed_concrete_value",
        ["id","effective_time","active","module_id","source_id","value","relationship_group","type_id","characteristic_type_id","modifier_id"],
        f"{TERM_DIR}/sct2_RelationshipConcreteValues_Snapshot_ArgentinaExtension_20251120.txt",
        lambda r: [r[0], r[1], bool_val(r[2]), r[3], r[4], safe(r[5]), r[6], r[7], r[8], r[9]],
        "concrete values")
    totals["snomed_concrete_value"] = n

    # Text Definitions
    n = copy_bulk(cur, conn, "snomed_text_definition",
        ["id","effective_time","active","module_id","concept_id","language_code","type_id","term","case_significance_id"],
        f"{TERM_DIR}/sct2_TextDefinition_Snapshot_ArgentinaExtension_20251120.txt",
        lambda r: [r[0], r[1], bool_val(r[2]), r[3], r[4], r[5], r[6], safe(r[7]), r[8]],
        "text definitions")
    totals["snomed_text_definition"] = n

    # OWL Expressions
    n = copy_bulk(cur, conn, "snomed_owl_expression",
        ["id","effective_time","active","module_id","refset_id","referenced_component_id","owl_expression"],
        f"{TERM_DIR}/sct2_sRefset_OWLExpressionSnapshot_ArgentinaExtension_20251120.txt",
        lambda r: [r[0], r[1], bool_val(r[2]), r[3], r[4], r[5], safe(r[6])],
        "OWL expressions")
    totals["snomed_owl_expression"] = n

    # =====================================================
    # SNAPSHOT / REFSET
    # =====================================================
    print("\n3. Loading Snapshot/Refset...")

    # Language
    lang_file = glob.glob(f"{SNAPSHOT}/Refset/Language/*Language*")[0]
    n = copy_bulk(cur, conn, "snomed_language",
        ["id","effective_time","active","module_id","refset_id","referenced_component_id","acceptability_id"],
        lang_file,
        lambda r: [r[0], r[1], bool_val(r[2]), r[3], r[4], r[5], r[6]],
        "language refset")
    totals["snomed_language"] = n

    # Extended Map (ICD-10)
    emap_file = glob.glob(f"{SNAPSHOT}/Refset/Map/*ExtendedMap*")[0]
    n = copy_bulk(cur, conn, "snomed_map_icd10",
        ["id","effective_time","active","module_id","refset_id","referenced_component_id","map_group","map_priority","map_rule","map_advice","map_target","correlation_id","map_category_id"],
        emap_file,
        lambda r: [r[0], r[1], bool_val(r[2]), r[3], r[4], r[5], r[6], r[7], safe(r[8]), safe(r[9]), r[10] if r[10] else '\\N', safe_bigint(r[11]), safe_bigint(r[12])],
        "ICD-10 extended maps")
    totals["snomed_map_icd10"] = n

    # Simple Map
    smap_file = glob.glob(f"{SNAPSHOT}/Refset/Map/*SimpleMap*")[0]
    n = copy_bulk(cur, conn, "snomed_map_simple",
        ["id","effective_time","active","module_id","refset_id","referenced_component_id","map_target"],
        smap_file,
        lambda r: [r[0], r[1], bool_val(r[2]), r[3], r[4], r[5], safe(r[6]) if len(r)>6 else '\\N'],
        "simple maps")
    totals["snomed_map_simple"] = n

    # Content - Simple Refset
    simple_file = glob.glob(f"{SNAPSHOT}/Refset/Content/*SimpleSnapshot*")[0]
    n = copy_bulk(cur, conn, "snomed_refset",
        ["id","effective_time","active","module_id","refset_id","referenced_component_id"],
        simple_file,
        lambda r: [r[0], r[1], bool_val(r[2]), r[3], r[4], r[5]],
        "simple refset members")
    totals["snomed_refset"] = n

    # Content - Association
    assoc_file = glob.glob(f"{SNAPSHOT}/Refset/Content/*Association*")[0]
    n = copy_bulk(cur, conn, "snomed_association",
        ["id","effective_time","active","module_id","refset_id","referenced_component_id","target_component_id"],
        assoc_file,
        lambda r: [r[0], r[1], bool_val(r[2]), r[3], r[4], r[5], r[6]],
        "association refset")
    totals["snomed_association"] = n

    # Content - Attribute Value
    attr_file = glob.glob(f"{SNAPSHOT}/Refset/Content/*AttributeValue*")[0]
    n = copy_bulk(cur, conn, "snomed_attribute_value",
        ["id","effective_time","active","module_id","refset_id","referenced_component_id","value_id"],
        attr_file,
        lambda r: [r[0], r[1], bool_val(r[2]), r[3], r[4], r[5], r[6]],
        "attribute value refset")
    totals["snomed_attribute_value"] = n

    # Content - Medicinal Products (6 component cols)
    med_file = glob.glob(f"{SNAPSHOT}/Refset/Content/*MedicinalProducts*")[0]
    n = copy_bulk(cur, conn, "snomed_medicinal_product",
        ["id","effective_time","active","module_id","refset_id","referenced_component_id",
         "component1_id","component2_id","component3_id","component4_id","component5_id","component6_id"],
        med_file,
        lambda r: [r[0], r[1], bool_val(r[2]), r[3], r[4], r[5],
                   safe_bigint(r[6]), safe_bigint(r[7]), safe_bigint(r[8]),
                   safe_bigint(r[9]), safe_bigint(r[10]), safe_bigint(r[11])],
        "medicinal products")
    totals["snomed_medicinal_product"] = n

    # =====================================================
    # RESOURCES (domain-specific refsets)
    # =====================================================
    print("\n4. Loading Resources (domain refsets)...")

    resource_total = 0
    resource_files = sorted(glob.glob(f"{RESOURCES}/*.txt"))
    for rf in resource_files:
        fname = os.path.basename(rf)
        if fname == ".DS_Store":
            continue
        # Resources have: id, effectiveTime, active, moduleId, refsetId, refsetId_term, referencedComponentId, referencedComponentId_term
        short_name = fname.split("-conjunto-de-")[0] if "-conjunto-de-" in fname else fname[:60]
        n = copy_bulk(cur, conn, "snomed_resource_refset",
            ["id","effective_time","active","module_id","refset_id","refset_name","referenced_component_id","referenced_component_term","source_file"],
            rf,
            lambda r, sf=fname: [r[0], r[1], bool_val(r[2]), r[3], r[4],
                        safe(r[5]) if len(r) > 5 else '\\N',
                        r[6] if len(r) > 6 else '\\N',
                        safe(r[7]) if len(r) > 7 else '\\N',
                        sf],
            f"resources: {short_name[:50]}")
        resource_total += n
    totals["snomed_resource_refset"] = resource_total

    elapsed = time.time() - t0
    print(f"\n   ⏱  Data loaded in {elapsed:.1f}s")

    # =====================================================
    # INDEXES
    # =====================================================
    print("\n5. Creating indexes...")
    t1 = time.time()
    for stmt in INDEXES.strip().split(";"):
        stmt = stmt.strip()
        if stmt and "CREATE INDEX" in stmt:
            name = stmt.split("INDEX ")[1].split(" ON")[0]
            cur.execute(f"DROP INDEX IF EXISTS {name}")
            cur.execute(stmt)
    conn.commit()
    print(f"   ✅ Indexes created in {time.time()-t1:.1f}s")

    # =====================================================
    # VIEWS
    # =====================================================
    print("\n6. Creating views...")
    cur.execute("""
    CREATE OR REPLACE VIEW v_snomed_procedimientos AS
    SELECT DISTINCT ON (d.concept_id)
        d.concept_id AS snomed_id,
        REPLACE(d.term, ' (procedimiento)', '') AS procedimiento,
        d.language_code
    FROM snomed_description d
    WHERE d.active AND d.language_code = 'es' AND d.term LIKE '%%(procedimiento)%%'
    ORDER BY d.concept_id, length(d.term);

    CREATE OR REPLACE VIEW v_snomed_trastornos AS
    SELECT DISTINCT ON (d.concept_id)
        d.concept_id AS snomed_id,
        REPLACE(d.term, ' (trastorno)', '') AS trastorno,
        d.language_code
    FROM snomed_description d
    WHERE d.active AND d.language_code = 'es' AND d.term LIKE '%%(trastorno)%%'
    ORDER BY d.concept_id, length(d.term);

    CREATE OR REPLACE VIEW v_snomed_hallazgos AS
    SELECT DISTINCT ON (d.concept_id)
        d.concept_id AS snomed_id,
        REPLACE(d.term, ' (hallazgo)', '') AS hallazgo,
        d.language_code
    FROM snomed_description d
    WHERE d.active AND d.language_code = 'es' AND d.term LIKE '%%(hallazgo)%%'
    ORDER BY d.concept_id, length(d.term);

    CREATE OR REPLACE VIEW v_snomed_especialidades AS
    SELECT DISTINCT ON (d.concept_id)
        d.concept_id AS snomed_id,
        REPLACE(d.term, ' (calificador)', '') AS especialidad,
        d.language_code
    FROM snomed_description d
    WHERE d.active AND d.language_code = 'es' AND d.term LIKE '%%(calificador)%%'
    ORDER BY d.concept_id, length(d.term);
    """)
    conn.commit()
    print("   ✅ Views created")

    # =====================================================
    # VERIFICATION
    # =====================================================
    print("\n7. VERIFICATION:")
    print("   " + "-" * 50)
    grand_total = 0
    for table in ["snomed_concept", "snomed_description", "snomed_relationship",
                   "snomed_stated_relationship", "snomed_concrete_value",
                   "snomed_text_definition", "snomed_owl_expression",
                   "snomed_language", "snomed_map_icd10", "snomed_map_simple",
                   "snomed_refset", "snomed_association", "snomed_attribute_value",
                   "snomed_medicinal_product", "snomed_resource_refset"]:
        cur.execute(f"SELECT count(*) FROM {table}")
        cnt = cur.fetchone()[0]
        grand_total += cnt
        status = "✅" if cnt > 0 else "⚠️ "
        print(f"   {status} {table:35s} {cnt:>10,}")
    print(f"   {'=' * 50}")
    print(f"   TOTAL ROWS: {grand_total:,}")

    # Sample queries
    print("\n8. Sample queries:")
    cur.execute("SELECT count(DISTINCT refset_id) FROM snomed_resource_refset")
    print(f"   Resource refsets: {cur.fetchone()[0]} distinct sets")
    
    cur.execute("""SELECT DISTINCT refset_name FROM snomed_resource_refset 
                   WHERE refset_name IS NOT NULL ORDER BY refset_name LIMIT 15""")
    for (name,) in cur.fetchall():
        print(f"   • {name[:80]}")

    cur.close()
    conn.close()
    print(f"\n✅ COMPLETE — Total time: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
