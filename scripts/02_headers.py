"""Saca las cabeceras de los TSV parseando CreateTables.sql y las deja en headers.json."""

import json
import urllib.request

import const

sql = urllib.request.urlopen(const.CREATE_TABLES_SQL).read().decode()
quiero = set(const.MB_CORE_TABLES + const.MB_DERIVED_TABLES)

headers = {}
tabla = None
depth = 0
for linea in sql.split("\n"):
    linea = linea.split("--")[0].rstrip()
    if linea.startswith("CREATE TABLE "):
        tabla = linea.split()[2]
        headers[tabla] = []
    elif tabla and depth == 1:
        # a profundidad 1, una linea que empieza en minuscula es una columna;
        # CHECK/CONSTRAINT van en mayusculas y los CHECK multilinea quedan a
        # profundidad >1 aunque contengan nombres de columna
        pal = linea.split()[0] if linea.split() else ""
        if pal and pal[0].islower():
            headers[tabla].append(pal)
    depth += linea.count("(") - linea.count(")")
    if tabla and depth == 0 and ");" in linea:
        tabla = None

headers = {t: headers[t] for t in quiero}

# si el DDL de master se desalineo con el dump, mejor reventar aqui que en la fase D
assert len(headers["artist"]) == 19, headers["artist"]
assert headers["artist"][-2:] == ["begin_area", "end_area"]
assert len(headers["recording"]) == 9, headers["recording"]

with open(f"{const.INTERIM}/headers.json", "w") as f:
    json.dump(headers, f, indent=1)

for t in sorted(headers):
    print(f"{t:<28} {len(headers[t]):>2}  {', '.join(headers[t])}")
