"""Carga los TSV de /data/interim en /data/mb.duckdb como tablas materializadas."""

import json
import os
import time

import duckdb

import const

headers = json.load(open(f"{const.INTERIM}/headers.json"))

# base nueva cada vez: recargar es barato comparado con debuggear una carga a medias
if os.path.exists(const.DUCKDB):
    os.remove(const.DUCKDB)
db = duckdb.connect(const.DUCKDB)
# sin esto duckdb intenta usar el 80% de la RAM y bufferea tablas enteras
# antes de escribirlas; con limite + temp_directory derrama a disco
db.execute("SET memory_limit='2GB'")
db.execute("SET preserve_insertion_order=false")
db.execute(f"SET temp_directory='{const.DUCKDB}.tmp'")

for tabla, cols in sorted(headers.items()):
    t = time.time()
    # formato COPY de Postgres: tab, sin comillas, \N como NULL.
    # sample_size=-1 infiere tipos con el archivo entero; con una muestra,
    # columnas casi-numericas con texto al final reventarian a mitad de carga
    db.execute(f"""
        CREATE TABLE {tabla} AS SELECT * FROM read_csv(
            '{const.INTERIM}/{tabla}', delim='\t', header=false, quote='',
            escape='', nullstr='\\N', sample_size=-1,
            names={cols})
    """)
    n = db.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0]
    print(f"{tabla:<28} {n:>12,}  {time.time() - t:5.0f} s")

db.execute(f"CREATE TABLE msd_mbid AS SELECT * FROM read_csv('{const.INTERIM}/msd_mbid.csv')")
n = db.execute("SELECT count(*) FROM msd_mbid").fetchone()[0]
print(f"{'msd_mbid':<28} {n:>12,}")

print("\nbase:", const.DUCKDB, f"{os.path.getsize(const.DUCKDB) / 1e9:.1f} GB")
