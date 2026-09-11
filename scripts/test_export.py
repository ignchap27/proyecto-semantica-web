"""Checks de la fase F. Correr tras `make 07`: python scripts/test_export.py"""

import duckdb

import const

P = const.PROCESSED
db = duckdb.connect()

n, dup = db.execute(f"""SELECT count(*), count(*) - count(DISTINCT track_id)
    FROM read_csv('{P}/songs_final.csv')""").fetchone()
assert n == 100_000, f"{n} filas"
assert dup == 0, f"{dup} track_id duplicados"

# las 7 columnas originales tienen que salir intactas
rotas = db.execute(f"""
    SELECT count(*)
    FROM read_csv('{const.SONGS_CSV}') g
    JOIN read_csv('{P}/songs_final.csv') s USING (track_id)
    WHERE s.title IS DISTINCT FROM g.title
       OR s.artist_name IS DISTINCT FROM g.artist_name
       OR s.release IS DISTINCT FROM g.release
       OR s.year IS DISTINCT FROM g.year
       OR s.duration IS DISTINCT FROM g.duration
       OR s.artist_mbid IS DISTINCT FROM g.artist_mbid""").fetchone()[0]
assert rotas == 0, f"{rotas} filas con columnas originales alteradas"

# coherencia del anio consolidado
mal = db.execute(f"""
    SELECT count(*) FROM read_csv('{P}/songs_final.csv')
    WHERE (year > 0 AND (anio IS DISTINCT FROM year OR fuente_anio != 'msd'))
       OR (fuente_anio = 'musicbrainz' AND year != 0)
       OR (anio IS NULL AND fuente_anio IS NOT NULL)""").fetchone()[0]
assert mal == 0, f"{mal} filas con anio/fuente_anio incoherentes"

mbid, n_match = db.execute(f"""
    SELECT (SELECT count(recording_mbid) FROM read_csv('{P}/songs_final.csv')),
           (SELECT count(*) FROM read_csv('{P}/matches.csv'))""").fetchone()
assert mbid == n_match, f"{mbid} mbids != {n_match} matches"

print(f"ok: {n:,} filas, originales intactas, anio coherente, "
      f"{mbid:,} recording_mbid = matches.csv")
