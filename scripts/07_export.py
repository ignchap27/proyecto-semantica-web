"""Exportacion final: songs_final.csv con las 100.000 filas + columnas enriquecidas."""

import os
import time

import duckdb

import const

t0 = time.time()
P = const.PROCESSED

# todo sale de los CSV de data/processed (las tablas de match en mb.duckdb son
# temporales y mueren si se repite make 03), asi que base en memoria
db = duckdb.connect()
db.execute("SET memory_limit='2GB'")
db.execute("SET preserve_insertion_order=false")
db.execute(f"SET temp_directory='{const.DUCKDB}.tmp'")

os.makedirs(P, exist_ok=True)

# joins 1:1 por track_id/artist_mbid; sellos y tags se agregan antes para no
# multiplicar filas
db.execute(f"""COPY (
    SELECT s.track_id, s.title, s.artist_name, s.release, s.year, s.duration,
           s.artist_mbid,
           m.recording_mbid, m.metodo AS metodo_match,
           CASE WHEN s.year > 0 THEN s.year ELSE r.anio END AS anio,
           CASE WHEN s.year > 0 THEN 'msd'
                WHEN r.anio IS NOT NULL THEN 'musicbrainz' END AS fuente_anio,
           r.release_mbid, r.titulo AS release_titulo, r.pais AS release_pais,
           r.tipo AS release_tipo,
           l.sellos,
           a.tipo AS artista_tipo, a.genero AS artista_genero,
           a.area AS artista_area, a.anio_inicio AS artista_anio_inicio,
           a.anio_fin AS artista_anio_fin, a.tags AS artista_tags,
           a.wikidata AS artista_wikidata,
           t.tags_grabacion,
           f.* EXCLUDE (track_id, recording_mbid, fuente)
    FROM read_csv('{const.SONGS_CSV}') s
    LEFT JOIN read_csv('{P}/matches.csv') m ON m.track_id = s.track_id
    LEFT JOIN read_csv('{P}/releases.csv') r ON r.track_id = s.track_id
    LEFT JOIN read_csv('{P}/artists.csv') a ON a.artist_mbid = s.artist_mbid
    LEFT JOIN (
        SELECT release_mbid, string_agg(nombre, ';' ORDER BY nombre) AS sellos
        FROM (SELECT DISTINCT release_mbid, nombre FROM read_csv('{P}/labels.csv'))
        GROUP BY 1
    ) l ON l.release_mbid = r.release_mbid
    LEFT JOIN (
        SELECT mbid, string_agg(tag, ';' ORDER BY rn) AS tags_grabacion
        FROM (
            SELECT mbid, tag, row_number() OVER (PARTITION BY mbid
                       ORDER BY votos DESC, tag) AS rn
            FROM read_csv('{P}/tags.csv') WHERE entidad = 'recording'
        ) WHERE rn <= {const.TOP_TAGS}
        GROUP BY 1
    ) t ON t.mbid = m.recording_mbid
    LEFT JOIN read_csv('{P}/features.csv') f ON f.track_id = s.track_id
    ORDER BY s.track_id
) TO '{P}/songs_final.csv' (HEADER)""")

n, dup, mbid, feats, rellenados, cols = db.execute(f"""
    SELECT count(*), count(*) - count(DISTINCT track_id), count(recording_mbid),
           count(bpm), sum((year = 0 AND anio IS NOT NULL)::INT),
           (SELECT count(*) FROM (DESCRIBE SELECT * FROM read_csv('{P}/songs_final.csv')))
    FROM read_csv('{P}/songs_final.csv')""").fetchone()
n_match = db.execute(f"SELECT count(*) FROM read_csv('{P}/matches.csv')").fetchone()[0]

print(f"songs_final.csv      {n:>9,} filas, {cols} columnas")
print(f"recording_mbid {mbid:>9,} ({mbid / n:.1%})")
print(f"features       {feats:>9,} ({feats / n:.1%})")
print(f"year=0 rellenados con el anio de la edicion: {rellenados:,}")

assert n == 100_000, f"{n} filas"
assert dup == 0, f"{dup} track_id duplicados"
assert mbid == n_match, f"{mbid} mbids != {n_match} matches"

print(f"total: {time.time() - t0:.0f} s")
