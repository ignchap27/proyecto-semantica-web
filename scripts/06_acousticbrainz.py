"""Features acusticas: extrae los tar.zst de AcousticBrainz y las cruza con el match."""

import glob
import os
import shutil
import subprocess
import time

import duckdb

import const

CATEGORIAS = ["lowlevel", "rhythm", "tonal"]

t0 = time.time()

# extraccion (una vez; si el parseo falla no se repite)
for cat, tar in zip(CATEGORIAS, const.AB_FEATURE_FILES):
    destino = f"{const.AB_DIR}/{cat}"
    if os.path.isdir(destino):
        continue
    t = time.time()
    os.makedirs(destino)
    subprocess.run(["tar", "-I", "zstd", "-xf", f"{const.RAW}/{tar}", "-C", destino],
                   check=True)
    print(f"extraido {cat} ({time.time() - t:.0f} s)")

# inspeccion: el formato interno no esta documentado
db = duckdb.connect(const.DUCKDB, read_only=True)
db.execute("SET memory_limit='2GB'")
db.execute("SET preserve_insertion_order=false")
db.execute(f"SET temp_directory='{const.DUCKDB}.tmp'")

globs = {}
for cat in CATEGORIAS:
    archivos = sorted(glob.glob(f"{const.AB_DIR}/{cat}/**/*.csv", recursive=True))
    assert archivos, f"sin CSVs en {const.AB_DIR}/{cat}; mirar que trae el tar"
    globs[cat] = f"{const.AB_DIR}/{cat}/**/*.csv"
    cols = db.execute(f"DESCRIBE SELECT * FROM read_csv('{archivos[0]}')").df()
    print(f"{cat}: {len(archivos)} archivos; columnas de {os.path.basename(archivos[0])}:")
    print("  " + ", ".join(cols["column_name"]))

# mbids objetivo: el actual del match + los viejos que redirigen a el
# (los mbid de AB son de <=2022, los nuestros del dump actual)
db.execute(f"""
    CREATE TEMP TABLE m AS
    SELECT track_id, recording_id, recording_mbid
    FROM read_csv('{const.PROCESSED}/matches.csv')""")
db.execute("""
    CREATE TEMP TABLE objetivo AS
    SELECT recording_mbid AS mbid_canon, recording_mbid AS mbid_ab FROM m
    UNION
    SELECT m.recording_mbid, g.gid
    FROM m JOIN recording_gid_redirect g ON g.new_id = m.recording_id
""")
n_obj = db.execute("SELECT count(*) FROM objetivo").fetchone()[0]
n_match = db.execute("SELECT count(*) FROM m").fetchone()[0]
print(f"objetivo: {n_obj:,} mbids para {n_match:,} matches")

# una submission por mbid canonico y categoria; la primera por offset, determinista
for cat in CATEGORIAS:
    t = time.time()
    db.execute(f"""
        CREATE TEMP TABLE ab_{cat} AS
        SELECT * EXCLUDE (rn) FROM (
            SELECT o.mbid_canon, ab.*,
                   row_number() OVER (PARTITION BY o.mbid_canon
                       ORDER BY ab.submission_offset) AS rn
            FROM read_csv('{globs[cat]}', union_by_name=true) ab
            JOIN objetivo o ON o.mbid_ab = ab.mbid
        ) WHERE rn = 1
    """)
    n = db.execute(f"SELECT count(*) FROM ab_{cat}").fetchone()[0]
    print(f"{cat:<9} {n:>7,} mbids con features  ({time.time() - t:.0f} s)")

db.execute(f"""
    COPY (
        SELECT m.track_id, m.recording_mbid,
               l.* EXCLUDE (mbid_canon, mbid, submission_offset),
               r.* EXCLUDE (mbid_canon, mbid, submission_offset),
               t.* EXCLUDE (mbid_canon, mbid, submission_offset),
               'acousticbrainz' AS fuente
        FROM m
        JOIN ab_lowlevel l ON l.mbid_canon = m.recording_mbid
        LEFT JOIN ab_rhythm r ON r.mbid_canon = m.recording_mbid
        LEFT JOIN ab_tonal t ON t.mbid_canon = m.recording_mbid
        ORDER BY m.track_id
    ) TO '{const.PROCESSED}/features.csv' (HEADER)
""")
n_feat = db.execute(
    f"SELECT count(*) FROM read_csv('{const.PROCESSED}/features.csv')").fetchone()[0]
dup = db.execute(f"""SELECT count(*) - count(DISTINCT track_id)
    FROM read_csv('{const.PROCESSED}/features.csv')""").fetchone()[0]
assert n_feat > 0, "features.csv vacio"
assert dup == 0, f"{dup} track_id duplicados en features"

# AB se congelo en 2022: la cobertura parcial es esperada, se mide y punto
print(f"\nfeatures.csv  {n_feat:,} / {n_match:,} matches = {n_feat / n_match:.1%}")

shutil.rmtree(const.AB_DIR)
print(f"limpiado {const.AB_DIR}")
print(f"total: {time.time() - t0:.0f} s")
