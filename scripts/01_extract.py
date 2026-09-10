"""Saca de los tarballs solo las tablas que usamos y las deja como TSV en /data/interim."""

import bz2
import os
import shutil
import subprocess
import sys
import time

import const


def extraer(tar, miembros):
    # patron */tabla en vez de mbdump/tabla: asi no dependemos de como se llame el
    # directorio raiz dentro del tar. tar compara el nombre completo, o sea que
    # */link no se lleva link_type por delante.
    # Un .bz2 no se puede saltar: aunque solo queramos 33 de las 236 tablas, el
    # stream se descomprime entero. lbzip2 lo hace en paralelo.
    t = time.time()
    subprocess.run(
        ["tar", "-x", "-I", "lbzip2", "-f", tar, "-C", const.INTERIM,
         "--strip-components=1", "--wildcards"] + [f"*/{m}" for m in miembros],
        check=True,
    )
    print(f"{os.path.basename(tar)}: {len(miembros)} miembros en {time.time() - t:.0f} s")


os.makedirs(const.INTERIM, exist_ok=True)

extraer(f"{const.RAW}/{const.MB_CORE_FILE}", const.MB_CORE_TABLES)
extraer(f"{const.RAW}/{const.MB_DERIVED_FILE}", const.MB_DERIVED_TABLES)

msd_bz2 = f"{const.RAW}/{const.MSD_MAP_URL.rsplit('/', 1)[1]}"
with bz2.open(msd_bz2, "rb") as f, open(f"{const.INTERIM}/msd_mbid.csv", "wb") as out:
    shutil.copyfileobj(f, out)

print("\ntabla                        filas        tamaño")
faltan = []
for tabla in const.MB_CORE_TABLES + const.MB_DERIVED_TABLES:
    path = f"{const.INTERIM}/{tabla}"
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        faltan.append(tabla)
        continue
    # el dump usa el formato COPY de Postgres, con \n escapado: 1 linea = 1 fila
    filas = subprocess.run(["wc", "-l", path], capture_output=True, text=True)
    mb = os.path.getsize(path) / 1e6
    print(f"{tabla:<25} {int(filas.stdout.split()[0]):>10,} {mb:>10,.0f} MB")

if faltan:
    sys.exit(f"faltan o estan vacias: {', '.join(faltan)}")
print("\nversion del dump:", open(f"{const.RAW}/MB_VERSION.txt").read().strip())
