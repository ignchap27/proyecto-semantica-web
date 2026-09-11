"""Checks de la fase D. Correr tras `make 04`: python scripts/test_match.py"""

import duckdb

import const

db = duckdb.connect(const.DUCKDB, read_only=True)

total = db.execute(f"SELECT count(*) FROM read_csv('{const.SONGS_CSV}')").fetchone()[0]
n = db.execute("SELECT count(*) FROM match").fetchone()[0]
assert n >= 0.60 * total, f"cobertura {n / total:.1%} < 60%"

dup = db.execute("SELECT count(*) - count(DISTINCT track_id) FROM match").fetchone()[0]
assert dup == 0, f"{dup} track_id duplicados en match"

huerfanos = db.execute("""
    SELECT count(*) FROM match m
    LEFT JOIN recording r ON r.gid = m.recording_mbid
    WHERE r.id IS NULL""").fetchone()[0]
assert huerfanos == 0, f"{huerfanos} mbid que no existen en recording"

# acuerdo laxo: mismo mbid, o mismo titulo normalizado + mismo artist_credit
# (duplicados sin fusionar de MB); el exacto ronda 57% solo por esos duplicados
db.execute("""CREATE TEMP MACRO norm(t) AS
    trim(regexp_replace(strip_accents(lower(t)), '[^a-z0-9]+', ' ', 'g'))""")
ambos, exacto, laxo = db.execute("""
    WITH ab AS (
        SELECT m.msd_track_id AS track_id, coalesce(r2.gid, m.recording_mbid) AS mbid
        FROM msd_mbid m
        LEFT JOIN recording_gid_redirect g ON g.gid = m.recording_mbid
        LEFT JOIN recording r2 ON r2.id = g.new_id)
    SELECT count(*), sum((mm.recording_mbid = ab.mbid)::INT),
           sum((mm.recording_mbid = ab.mbid
                OR (norm(rn.name) = norm(rs.name)
                    AND rn.artist_credit = rs.artist_credit))::INT)
    FROM match mm
    JOIN ab USING (track_id)
    JOIN recording rn ON rn.gid = mm.recording_mbid
    LEFT JOIN recording rs ON rs.gid = ab.mbid""").fetchone()
assert laxo >= 0.75 * ambos, f"acuerdo laxo con AB {laxo / ambos:.1%} < 75%"

print(f"ok: cobertura {n / total:.1%}, sin duplicados, mbids validos, "
      f"acuerdo AB exacto {exacto / ambos:.1%} / laxo {laxo / ambos:.1%} "
      f"sobre {ambos:,} filas")
