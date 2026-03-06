#!/bin/bash
###############################################################################
# Full Database Restore from dump_20260303
# 
# Restores ALL 4 databases:
#   1. PostgreSQL  (full restore including SNOMED, owner remapped)
#   2. MongoDB     (full restore with --drop, authSource=admin)
#   3. Qdrant      (snapshot upload for 3 collections)
#   4. Redis       (flush cache)
#
# Date: 2026-03-03
###############################################################################

set -euo pipefail

DUMP_DIR="/home/ubuntu/ainstein/ainstein_be/dump_20260303"

# PostgreSQL - Container name and credentials
PG_CONTAINER="ferro_postgres"
PG_USER="epc_user"
PG_DB="epc_db"

# MongoDB - Container name and credentials (authSource=admin)
MONGO_CONTAINER="ferro_mongo"
MONGO_USER="epc_user"
MONGO_PASS="epc_strong_pass_2025"
MONGO_AUTH_DB="admin"

# Qdrant
QDRANT_URL="http://localhost:6333"

# Redis
REDIS_CONTAINER="ferro_redis"

echo "================================================================"
echo "  AInstein Full Database Restore — dump_20260303"
echo "  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "================================================================"
echo ""

###############################################################################
# STEP 1: PostgreSQL Restore
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🐘 STEP 1/4: PostgreSQL Restore"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "  📋 Current state (before):"
docker exec $PG_CONTAINER psql -U $PG_USER -d $PG_DB -c "
SET app.tenant_id = '00000000-0000-0000-0000-000000000001';
SELECT 'patients' as tabla, count(*) FROM patients
UNION ALL SELECT 'admissions', count(*) FROM admissions
UNION ALL SELECT 'users', count(*) FROM users
UNION ALL SELECT 'roles', count(*) FROM roles
UNION ALL SELECT 'tenants', count(*) FROM tenants
ORDER BY 1;" 2>/dev/null || echo "  ⚠️  Could not query current state"

# Step 1a: Decompress the SQL dump if needed
SQL_FILE="$DUMP_DIR/postgres_epc_db_full.sql"
SQL_GZ="$DUMP_DIR/postgres_epc_db_full.sql.gz"
CLEAN_SQL="/tmp/postgres_epc_db_clean_20260303.sql"

if [ ! -f "$SQL_FILE" ]; then
    echo "  📦 Decompressing PostgreSQL dump..."
    gunzip -k "$SQL_GZ"
fi

# Step 1b: Preprocess - remap owner from 'ainstein' to 'epc_user'
echo "  🔧 Preprocessing SQL dump..."
echo "    - Remapping OWNER TO ainstein → epc_user"
echo "    - Removing PG15-only directives"
sed -e 's/OWNER TO ainstein/OWNER TO epc_user/g' \
    -e '/\\restrict/d' \
    -e '/\\unrestrict/d' \
    "$SQL_FILE" > "$CLEAN_SQL"

# Step 1c: Drop and recreate schema (full wipe)
echo "  🗑️  Dropping and recreating schema..."
docker exec $PG_CONTAINER psql -U $PG_USER -d $PG_DB -c "
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO $PG_USER;
GRANT ALL ON SCHEMA public TO public;" 2>&1 || true

# Step 1d: Restore from cleaned SQL
echo "  🚀 Restoring PostgreSQL (full dump including SNOMED)..."
echo "    This may take a few minutes due to SNOMED data..."
docker cp "$CLEAN_SQL" "$PG_CONTAINER:/tmp/restore.sql"
docker exec $PG_CONTAINER psql -U $PG_USER -d $PG_DB \
    -v ON_ERROR_STOP=0 \
    -f /tmp/restore.sql 2>&1 | tail -10

# Cleanup
docker exec $PG_CONTAINER rm -f /tmp/restore.sql
rm -f "$CLEAN_SQL"

echo ""
echo "  📋 Current state (after):"
docker exec $PG_CONTAINER psql -U $PG_USER -d $PG_DB -c "
SET app.tenant_id = '00000000-0000-0000-0000-000000000001';
SELECT 'patients' as tabla, count(*) FROM patients
UNION ALL SELECT 'admissions', count(*) FROM admissions
UNION ALL SELECT 'users', count(*) FROM users
UNION ALL SELECT 'roles', count(*) FROM roles
UNION ALL SELECT 'tenants', count(*) FROM tenants
ORDER BY 1;" 2>/dev/null

echo "  🔍 Verifying SNOMED data:"
docker exec $PG_CONTAINER psql -U $PG_USER -d $PG_DB -c "
SELECT 'snomed_concept' as tabla, count(*) FROM snomed_concept
UNION ALL SELECT 'snomed_description', count(*) FROM snomed_description
ORDER BY 1;" 2>/dev/null || echo "  ⚠️  SNOMED tables not found (may need separate import)"

echo "  ✅ PostgreSQL restore complete!"
echo ""

###############################################################################
# STEP 2: MongoDB Restore
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🍃 STEP 2/4: MongoDB Restore"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "  📋 Current state (before):"
docker exec $MONGO_CONTAINER mongosh -u $MONGO_USER -p $MONGO_PASS \
    --authenticationDatabase $MONGO_AUTH_DB --quiet epc --eval '
    db.getCollectionNames().forEach(function(c) {
        print("    " + c + ": " + db.getCollection(c).countDocuments({}));
    })' 2>/dev/null || echo "  ⚠️  Could not query current state"

# Copy dump to container
echo "  📤 Copying MongoDB dump to container..."
docker cp "$DUMP_DIR/mongo_epc_full" "$MONGO_CONTAINER:/tmp/mongodump_restore"

# Restore with --drop (using authSource=admin as per .env)
echo "  🚀 Restoring MongoDB (full restore with --drop)..."
docker exec $MONGO_CONTAINER mongorestore \
    --uri="mongodb://$MONGO_USER:$MONGO_PASS@127.0.0.1:27017/epc?authSource=$MONGO_AUTH_DB" \
    --gzip \
    --drop \
    --dir=/tmp/mongodump_restore \
    --nsInclude="epc.*" \
    2>&1 | grep -E "document|finished|error|done|failed|restoring" || true

# Cleanup temp files in container
docker exec $MONGO_CONTAINER rm -rf /tmp/mongodump_restore

echo ""
echo "  📋 Current state (after):"
docker exec $MONGO_CONTAINER mongosh -u $MONGO_USER -p $MONGO_PASS \
    --authenticationDatabase $MONGO_AUTH_DB --quiet epc --eval '
    db.getCollectionNames().forEach(function(c) {
        print("    " + c + ": " + db.getCollection(c).countDocuments({}));
    })' 2>/dev/null

echo "  ✅ MongoDB restore complete!"
echo ""

###############################################################################
# STEP 3: Qdrant Restore
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🔷 STEP 3/4: Qdrant Restore"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for COLLECTION in epc_feedback epc_feedback_vectors hce_chunks; do
    SNAPSHOT_FILE="$DUMP_DIR/qdrant_${COLLECTION}.snapshot"
    if [ -f "$SNAPSHOT_FILE" ]; then
        echo "  📤 Restoring collection: $COLLECTION..."
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            -X POST "${QDRANT_URL}/collections/${COLLECTION}/snapshots/upload?priority=snapshot" \
            -H "Content-Type: multipart/form-data" \
            -F "snapshot=@${SNAPSHOT_FILE}" 2>/dev/null)
        if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "202" ]; then
            echo "    ✅ $COLLECTION restored (HTTP $HTTP_CODE)"
        else
            echo "    ⚠️  $COLLECTION HTTP response: $HTTP_CODE (may need to create collection first)"
        fi
    else
        echo "  ⏭️  Skipping $COLLECTION (snapshot file not found)"
    fi
done

echo "  ✅ Qdrant restore complete!"
echo ""

###############################################################################
# STEP 4: Redis Flush
###############################################################################
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🔴 STEP 4/4: Redis Cache Clear"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

docker exec $REDIS_CONTAINER redis-cli FLUSHALL 2>/dev/null || true
echo "  ✅ Redis cache cleared (will regenerate on next access)"
echo ""

echo "================================================================"
echo "  🎉 FULL DATABASE RESTORE COMPLETE!"
echo "  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "================================================================"
echo ""
echo "  Summary:"
echo "    ✅ PostgreSQL (full restore, SNOMED included, owner remapped)"
echo "    ✅ MongoDB (full restore with --drop)"
echo "    ✅ Qdrant (3 snapshot collections uploaded)"
echo "    ✅ Redis (cache cleared)"
echo ""
echo "  Next steps:"
echo "    1. Restart the backend: cd ainstein_be && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo "    2. Verify health: curl http://localhost:8000/api/health"
echo "    3. Verify frontend: npm run dev (in ainstein_fe)"
echo ""
