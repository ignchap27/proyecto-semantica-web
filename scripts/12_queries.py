"""Corre queries/cqN.rq contra Fuseki y guarda el resultado real en docs/resultados/cqN.csv."""
import glob
import os
import time
import urllib.parse
import urllib.request

import configuracion as cfg

os.makedirs("docs/resultados", exist_ok=True)
for ruta in sorted(glob.glob("queries/cq*.rq")):
    nombre = os.path.basename(ruta)[:-3]
    q = open(ruta, encoding="utf-8").read()
    r = urllib.request.Request(cfg.QUERY, data=urllib.parse.urlencode({"query": q}).encode(),
                               headers={"Accept": "text/csv"})
    t0 = time.time()
    with urllib.request.urlopen(r, timeout=3600) as resp:
        csv = resp.read().decode("utf-8")
    open(f"docs/resultados/{nombre}.csv", "w", encoding="utf-8").write(csv)
    filas = csv.strip().splitlines()
    print(f"\n=== {nombre}: {len(filas) - 1} filas en {time.time() - t0:.1f} s")
    print("\n".join(filas[:6]))
