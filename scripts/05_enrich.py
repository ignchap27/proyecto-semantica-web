"""Enriquecimiento desde MusicBrainz: artists, releases, labels, tags y urls."""

import os
import time

import duckdb

import const

t0 = time.time()
db = duckdb.connect(const.DUCKDB, read_only=True)
db.execute("SET memory_limit='2GB'")
db.execute("SET preserve_insertion_order=false")
db.execute(f"SET temp_directory='{const.DUCKDB}.tmp'")

db.execute(f"""CREATE TEMP TABLE m AS
    SELECT track_id, recording_id, recording_mbid
    FROM read_csv('{const.PROCESSED}/matches.csv')""")
n_match = db.execute("SELECT count(*) FROM m").fetchone()[0]

# mismo patron que 04: mbid del MSD -> artist.id, con redirect para los fusionados
db.execute(f"""
    CREATE TEMP TABLE artista AS
    SELECT s.artist_mbid, coalesce(a.id, a2.id) AS artist_id
    FROM (SELECT DISTINCT artist_mbid FROM read_csv('{const.SONGS_CSV}')) s
    LEFT JOIN artist a ON a.gid = s.artist_mbid
    LEFT JOIN artist_gid_redirect g ON g.gid = s.artist_mbid
    LEFT JOIN artist a2 ON a2.id = g.new_id
    WHERE coalesce(a.id, a2.id) IS NOT NULL
""")

os.makedirs(const.PROCESSED, exist_ok=True)


def exporta(nombre, sql):
    t = time.time()
    db.execute(f"COPY ({sql}) TO '{const.PROCESSED}/{nombre}.csv' (HEADER)")
    n = db.execute(f"SELECT count(*) FROM read_csv('{const.PROCESSED}/{nombre}.csv')").fetchone()[0]
    print(f"{nombre + '.csv':<14} {n:>9,} filas  ({time.time() - t:.0f} s)")
    return n


n_art = exporta("artists", f"""
    SELECT ar.artist_mbid, a.gid AS mbid_canonico, a.name AS nombre,
           a.sort_name AS nombre_orden, ty.name AS tipo, ge.name AS genero,
           aa.name AS area, a.begin_date_year AS anio_inicio,
           a.end_date_year AS anio_fin, tg.tags, wd.wikidata,
           'musicbrainz' AS fuente
    FROM artista ar
    JOIN artist a ON a.id = ar.artist_id
    LEFT JOIN artist_type ty ON ty.id = a.type
    LEFT JOIN gender ge ON ge.id = a.gender
    LEFT JOIN area aa ON aa.id = a.area
    LEFT JOIN (
        SELECT artist, string_agg(name, ';' ORDER BY rn) AS tags
        FROM (
            SELECT at2.artist, t.name,
                   row_number() OVER (PARTITION BY at2.artist
                       ORDER BY at2.count DESC, t.name) AS rn
            FROM artist_tag at2
            JOIN tag t ON t.id = at2.tag
            WHERE at2.count > 0
              AND at2.artist IN (SELECT artist_id FROM artista)
        ) WHERE rn <= {const.TOP_TAGS}
        GROUP BY artist
    ) tg ON tg.artist = a.id
    LEFT JOIN (
        SELECT lau.entity0 AS artist, min(u.url) AS wikidata
        FROM l_artist_url lau
        JOIN link l ON l.id = lau.link
        JOIN link_type lt ON lt.id = l.link_type
        JOIN url u ON u.id = lau.entity1
        WHERE lt.name = 'wikidata'
        GROUP BY 1
    ) wd ON wd.artist = a.id
    ORDER BY ar.artist_mbid
""")

# edicion mas antigua por recording, prefiriendo las oficiales (status 1) pero sin
# descartar recordings que solo tienen bootlegs o promos
db.execute("""
    CREATE TEMP TABLE rel AS
    SELECT * FROM (
        SELECT m.track_id, m.recording_mbid, r.id AS release_id,
               r.gid AS release_mbid, r.name AS titulo, rc.date_year AS anio,
               rc.date_month AS mes, ap.name AS pais, rg.id AS rg_id,
               rg.gid AS release_group_mbid, pt.name AS tipo,
               row_number() OVER (PARTITION BY m.track_id
                   ORDER BY (rc.date_year IS NULL), (r.status IS DISTINCT FROM 1),
                            rc.date_year, rc.date_month, rc.date_day, r.id) AS rn
        FROM m
        JOIN track t ON t.recording = m.recording_id
        JOIN medium md ON md.id = t.medium
        JOIN release r ON r.id = md.release
        JOIN release_group rg ON rg.id = r.release_group
        LEFT JOIN release_country rc ON rc.release = r.id
        LEFT JOIN area ap ON ap.id = rc.country
        LEFT JOIN release_group_primary_type pt ON pt.id = rg.type
    ) WHERE rn = 1
""")
n_rel = exporta("releases", """
    SELECT track_id, recording_mbid, release_mbid, titulo, anio, mes, pais,
           release_group_mbid, tipo, 'musicbrainz' AS fuente
    FROM rel ORDER BY track_id
""")

exporta("labels", """
    SELECT DISTINCT r.release_mbid, lb.gid AS label_mbid, lb.name AS nombre,
           rl.catalog_number AS catalogo, 'musicbrainz' AS fuente
    FROM (SELECT DISTINCT release_id, release_mbid FROM rel) r
    JOIN release_label rl ON rl.release = r.release_id
    JOIN label lb ON lb.id = rl.label
    ORDER BY release_mbid, label_mbid
""")

# recording_tag es escaso; los tags de release_group compensan
exporta("tags", """
    SELECT 'recording' AS entidad, m.recording_mbid AS mbid, t.name AS tag,
           rt.count AS votos, 'musicbrainz-derived' AS fuente
    FROM m
    JOIN recording_tag rt ON rt.recording = m.recording_id
    JOIN tag t ON t.id = rt.tag
    WHERE rt.count > 0
    UNION ALL
    SELECT 'release_group', r.release_group_mbid, t.name, rgt.count,
           'musicbrainz-derived'
    FROM (SELECT DISTINCT rg_id, release_group_mbid FROM rel) r
    JOIN release_group_tag rgt ON rgt.release_group = r.rg_id
    JOIN tag t ON t.id = rgt.tag
    WHERE rgt.count > 0
    ORDER BY 1, 2, 4 DESC
""")

exporta("urls", """
    SELECT DISTINCT 'artist' AS entidad, a.gid AS mbid, lt.name AS tipo, u.url,
           'musicbrainz' AS fuente
    FROM artista ar
    JOIN artist a ON a.id = ar.artist_id
    JOIN l_artist_url lx ON lx.entity0 = ar.artist_id
    JOIN link l ON l.id = lx.link
    JOIN link_type lt ON lt.id = l.link_type
    JOIN url u ON u.id = lx.entity1
    UNION
    SELECT DISTINCT 'release', r.release_mbid, lt.name, u.url, 'musicbrainz'
    FROM (SELECT DISTINCT release_id, release_mbid FROM rel) r
    JOIN l_release_url lx ON lx.entity0 = r.release_id
    JOIN link l ON l.id = lx.link
    JOIN link_type lt ON lt.id = l.link_type
    JOIN url u ON u.id = lx.entity1
    UNION
    SELECT DISTINCT 'release_group', r.release_group_mbid, lt.name, u.url,
           'musicbrainz'
    FROM (SELECT DISTINCT rg_id, release_group_mbid FROM rel) r
    JOIN l_release_group_url lx ON lx.entity0 = r.rg_id
    JOIN link l ON l.id = lx.link
    JOIN link_type lt ON lt.id = l.link_type
    JOIN url u ON u.id = lx.entity1
    ORDER BY 1, 2, 3
""")

assert n_art >= 26_000, f"solo {n_art} artistas"
dup = db.execute(f"""SELECT count(*) - count(DISTINCT artist_mbid)
    FROM read_csv('{const.PROCESSED}/artists.csv')""").fetchone()[0]
assert dup == 0, f"{dup} artist_mbid duplicados"
dup = db.execute("SELECT count(*) - count(DISTINCT track_id) FROM rel").fetchone()[0]
assert dup == 0, f"{dup} track_id duplicados en releases"

print(f"\nreleases: {n_rel:,} / {n_match:,} matches = {n_rel / n_match:.1%} con edicion")
print(f"total: {time.time() - t0:.0f} s")
