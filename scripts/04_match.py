"""Matching track_id -> recording MBID: candidatos por artista, titulo normalizado + duracion."""

import os
import time

import duckdb
import pandas as pd
from rapidfuzz import fuzz, process

import const

MUESTRA = int(os.environ.get("MUESTRA", "0"))  # >0 = probar con N filas

t0 = time.time()
db = duckdb.connect(const.DUCKDB)
db.execute("SET memory_limit='2GB'")
db.execute("SET preserve_insertion_order=false")
db.execute(f"SET temp_directory='{const.DUCKDB}.tmp'")

# minusculas, sin acentos, solo alfanumerico
db.execute("""CREATE OR REPLACE MACRO norm(t) AS
    trim(regexp_replace(strip_accents(lower(t)), '[^a-z0-9]+', ' ', 'g'))""")

# tnorm_ss: sin el sufijo entre parentesis tipo "(Album Version)" que abunda en el MSD
limit = f"LIMIT {MUESTRA}" if MUESTRA else ""
db.execute(f"""
    CREATE OR REPLACE TEMP TABLE songs AS
    SELECT *, norm(title) AS tnorm,
           norm(regexp_replace(title, '\\s*\\([^)]*\\)\\s*$', '')) AS tnorm_ss
    FROM read_csv('{const.SONGS_CSV}') {limit}
""")
n_songs = db.execute("SELECT count(*) FROM songs").fetchone()[0]
print(f"canciones: {n_songs:,}")

# los MBID del MSD son de ~2010: los artistas fusionados se resuelven por redirect
db.execute("""
    CREATE OR REPLACE TEMP TABLE artista AS
    SELECT s.artist_mbid, coalesce(a.id, a2.id) AS artist_id,
           (a.id IS NULL AND a2.id IS NOT NULL) AS por_redirect
    FROM (SELECT DISTINCT artist_mbid FROM songs) s
    LEFT JOIN artist a ON a.gid = s.artist_mbid
    LEFT JOIN artist_gid_redirect g ON g.gid = s.artist_mbid
    LEFT JOIN artist a2 ON a2.id = g.new_id
""")
directo, redirect, sin = db.execute("""
    SELECT sum((artist_id IS NOT NULL AND NOT por_redirect)::INT),
           sum(por_redirect::INT), sum((artist_id IS NULL)::INT)
    FROM artista""").fetchone()
print(f"artistas: {directo:,} directos, {redirect:,} por redirect, {sin:,} sin resolver "
      f"({time.time() - t0:.0f} s)")

t = time.time()
db.execute("""
    CREATE OR REPLACE TEMP TABLE candidatos AS
    SELECT acn.artist AS artist_id, r.id AS recording_id, r.gid AS recording_mbid,
           norm(r.name) AS tnorm, r.length
    FROM recording r
    JOIN artist_credit_name acn ON acn.artist_credit = r.artist_credit
    WHERE acn.artist IN (SELECT artist_id FROM artista WHERE artist_id IS NOT NULL)
""")
# popularidad: MB esta lleno de recordings duplicados (mismo titulo, mismo artista,
# distinto mbid); el que mas tracks referencia es el canonico y desempata mejor
db.execute("""
    CREATE OR REPLACE TEMP TABLE n_tracks AS
    SELECT recording, count(*) AS n FROM track
    WHERE recording IN (SELECT recording_id FROM candidatos)
    GROUP BY recording
""")
n_cand = db.execute("SELECT count(*) FROM candidatos").fetchone()[0]
print(f"candidatos: {n_cand:,} recordings ({time.time() - t:.0f} s)")

db.execute("""CREATE OR REPLACE TABLE match (
    track_id VARCHAR, recording_id BIGINT, recording_mbid VARCHAR,
    metodo VARCHAR, score DOUBLE)""")


def casar(col, metodo):
    # empate: duracion dentro de tolerancia primero (length en ms, duration en s),
    # luego el recording mas referenciado, luego menor diferencia de duracion
    t = time.time()
    db.execute(f"""
        INSERT INTO match
        SELECT track_id, recording_id, recording_mbid, '{metodo}', 100.0
        FROM (
            SELECT s.track_id, c.recording_id, c.recording_mbid,
                   row_number() OVER (PARTITION BY s.track_id
                       ORDER BY (c.length IS NULL),
                                (abs(c.length - s.duration * 1000)
                                 > {const.DURATION_TOLERANCE_S * 1000}),
                                coalesce(nt.n, 0) DESC,
                                abs(c.length - s.duration * 1000),
                                c.recording_id) AS rn
            FROM songs s
            JOIN artista a USING (artist_mbid)
            JOIN candidatos c ON c.artist_id = a.artist_id AND c.tnorm = s.{col}
            LEFT JOIN n_tracks nt ON nt.recording = c.recording_id
            WHERE s.{col} <> ''
              AND s.track_id NOT IN (SELECT track_id FROM match)
        ) WHERE rn = 1
    """)
    n = db.execute("SELECT count(*) FROM match WHERE metodo = ?", [metodo]).fetchone()[0]
    print(f"{metodo:<12} {n:>7,}  ({time.time() - t:.0f} s)")


casar("tnorm", "exacto")
casar("tnorm_ss", "sin_sufijo")

# fuzzy solo sobre el remanente, con guardia de duracion (sin length no hay guardia)
t = time.time()
db.execute("""
    CREATE OR REPLACE TEMP TABLE pendiente AS
    SELECT s.track_id, s.tnorm, s.duration, a.artist_id
    FROM songs s JOIN artista a USING (artist_mbid)
    WHERE a.artist_id IS NOT NULL AND s.tnorm <> ''
      AND s.track_id NOT IN (SELECT track_id FROM match)
""")
pend = db.execute("SELECT * FROM pendiente").df()
cand = db.execute("""
    SELECT artist_id, recording_id, recording_mbid, tnorm, length FROM candidatos
    WHERE length IS NOT NULL
      AND artist_id IN (SELECT DISTINCT artist_id FROM pendiente)
""").df()
grupos = dict(tuple(cand.groupby("artist_id")))

filas = []
for s in pend.itertuples():
    g = grupos.get(s.artist_id)
    if g is None:
        continue
    g = g[(g["length"] - s.duration * 1000).abs() <= const.DURATION_TOLERANCE_S * 1000]
    if g.empty:
        continue
    hit = process.extractOne(s.tnorm, g["tnorm"].tolist(),
                             scorer=fuzz.token_set_ratio,
                             score_cutoff=const.FUZZY_THRESHOLD)
    if hit:
        c = g.iloc[hit[2]]
        filas.append((s.track_id, int(c.recording_id), c.recording_mbid, "fuzzy", hit[1]))

if filas:
    fdf = pd.DataFrame(filas, columns=["track_id", "recording_id", "recording_mbid",
                                       "metodo", "score"])
    db.execute("INSERT INTO match SELECT * FROM fdf")
print(f"{'fuzzy':<12} {len(filas):>7,}  ({time.time() - t:.0f} s, "
      f"{len(pend):,} pendientes)")

total = db.execute("SELECT count(*) FROM match").fetchone()[0]
print(f"\ncobertura: {total:,} / {n_songs:,} = {total / n_songs:.1%}")

os.makedirs(const.PROCESSED, exist_ok=True)
db.execute(f"""COPY (SELECT * FROM match ORDER BY track_id)
               TO '{const.PROCESSED}/matches.csv' (HEADER)""")

# la fase C cargo msd_mbid sin names= y el sniffer se comio la primera fila como
# cabecera; se recarga aqui (13 MB) para no repetir los 16 min de la carga completa
db.execute(f"""CREATE OR REPLACE TABLE msd_mbid AS SELECT * FROM read_csv(
    '{const.INTERIM}/msd_mbid.csv', header=false,
    names=['msd_track_id', 'recording_mbid', 'titulo', 'artista'])""")

# contraste con el mapeo MSD->MBID de AcousticBrainz. Sus MBID son de 2016:
# se canonicalizan por recording_gid_redirect antes de comparar
db.execute("""
    CREATE OR REPLACE TEMP TABLE ab AS
    SELECT m.msd_track_id AS track_id, coalesce(r2.gid, m.recording_mbid) AS mbid
    FROM msd_mbid m
    LEFT JOIN recording_gid_redirect g ON g.gid = m.recording_mbid
    LEFT JOIN recording r2 ON r2.id = g.new_id
    WHERE m.msd_track_id IN (SELECT track_id FROM songs)
""")
# acuerdo laxo: MBID distinto pero mismo titulo normalizado y mismo artist_credit
# = recordings duplicados sin fusionar en MB, no un error de matching
n_ab, ambos, acuerdo, laxo = db.execute("""
    SELECT count(*), count(mm.track_id),
           sum((mm.recording_mbid = ab.mbid)::INT),
           sum((mm.recording_mbid = ab.mbid
                OR (norm(rn.name) = norm(rs.name)
                    AND rn.artist_credit = rs.artist_credit))::INT)
    FROM ab
    LEFT JOIN match mm USING (track_id)
    LEFT JOIN recording rn ON rn.gid = mm.recording_mbid
    LEFT JOIN recording rs ON rs.gid = ab.mbid""").fetchone()
print(f"\ncontraste AB: mapeo cubre {n_ab:,} de nuestras filas; "
      f"{ambos:,} con match propio; acuerdo exacto {acuerdo:,} ({acuerdo / ambos:.1%}), "
      f"laxo {laxo:,} ({laxo / ambos:.1%})")
print(db.execute("""
    SELECT mm.metodo, count(*) AS n, sum((mm.recording_mbid = ab.mbid)::INT) AS acuerdo
    FROM match mm JOIN ab USING (track_id) GROUP BY 1 ORDER BY 2 DESC""").df()
      .to_string(index=False))

print(f"\ntotal: {time.time() - t0:.0f} s")
