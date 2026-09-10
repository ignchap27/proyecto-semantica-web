"""Baja los dumps a /data/raw y verifica los checksums publicados.

Reejecutable: lo que ya esta y cuadra no se vuelve a bajar.
"""

import bz2
import hashlib
import os
import subprocess
import sys
import urllib.request

import const

# el mirror se queda colgado a mitad de descarga cada tanto: si baja de 10 kB/s
# durante un minuto, corta y reintenta (con -C - retoma donde iba)
CURL = ["curl", "-fL", "--retry", "10", "--retry-delay", "5", "--retry-all-errors",
        "--speed-limit", "10240", "--speed-time", "60"]


def texto(url):
    with urllib.request.urlopen(url) as r:
        return r.read().decode()


def hash_archivo(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def parse_sums(txt):
    # MD5SUMS viene como "<hash> *<archivo>" y sha256sums como "<hash>  <archivo>"
    sums = {}
    for linea in txt.split("\n"):
        if linea.strip():
            h, nombre = linea.split(None, 1)
            sums[nombre.strip().lstrip("*")] = h
    return sums


def bajar(url, sums):
    nombre = url.rsplit("/", 1)[1]
    dest = f"{const.RAW}/{nombre}"
    esperado = sums.get(nombre)
    algo = "md5" if esperado and len(esperado) == 32 else "sha256"

    if esperado and os.path.exists(dest) and hash_archivo(dest, algo) == esperado:
        print(f"OK   {nombre} (ya estaba)")
        return dest

    # -C - reanuda: con 7 GB la conexion se cae mas de lo que uno quisiera.
    # Si el archivo local ya esta completo el servidor responde 416 y curl falla;
    # en ese caso lo bajamos entero de nuevo (estaba completo pero corrupto).
    if subprocess.run(CURL + ["-C", "-", "-o", dest, url]).returncode:
        subprocess.run(CURL + ["-o", dest, url], check=True)

    if not esperado:
        print(f"--   {nombre} (sin checksum publicado)")
        return dest

    got = hash_archivo(dest, algo)
    if got != esperado:
        os.remove(dest)
        sys.exit(f"ERROR {algo} de {nombre}: esperaba {esperado}, dio {got}")
    print(f"OK   {nombre}")
    return dest


os.makedirs(const.RAW, exist_ok=True)

version = texto(const.MB_LATEST_URL).strip()
print(f"fullexport de MusicBrainz: {version}")
base = f"{const.MB_FULLEXPORT}/{version}"
open(f"{const.RAW}/MB_VERSION.txt", "w").write(version + "\n")

mb_sums = parse_sums(texto(f"{base}/{const.MB_MD5SUMS}"))
ab_sums = parse_sums(texto(f"{const.AB_FEATURES}/{const.AB_SHA256SUMS}"))

bajar(f"{base}/{const.MB_CORE_FILE}", mb_sums)
bajar(f"{base}/{const.MB_DERIVED_FILE}", mb_sums)
for f in const.AB_FEATURE_FILES:
    bajar(f"{const.AB_FEATURES}/{f}", ab_sums)

# el mapeo MSD no tiene checksum publicado; vale si bz2 lo abre y trae cabecera
msd = bajar(const.MSD_MAP_URL, {})
with bz2.open(msd, "rt") as f:
    print("primera linea del mapeo MSD:", f.readline().strip()[:80])
