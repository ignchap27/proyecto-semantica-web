"""Carga ontology.ttl + instances.ttl en el grafo por defecto de Fuseki (Graph Store Protocol)."""
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import configuracion as cfg
import const


def pedir(url, data=None, metodo="GET", tipo=None, largo=None):
    r = urllib.request.Request(url, data=data, method=metodo)
    if tipo:
        r.add_header("Content-Type", tipo)
    if largo is not None:
        r.add_header("Content-Length", str(largo))
    # la imagen de Fuseki pide usuario tambien para escribir en el dataset
    r.add_header("Authorization", "Basic " + base64.b64encode(cfg.ADMIN.encode()).decode())
    with urllib.request.urlopen(r, timeout=3600) as resp:
        return resp.read()


def contar(q):
    url = cfg.QUERY + "?" + urllib.parse.urlencode({"query": q})
    r = urllib.request.Request(url, headers={"Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(r) as resp:
        return int(json.load(resp)["results"]["bindings"][0]["n"]["value"])


# recargar = borrar el dataset y crearlo de nuevo: vaciar 2,5 M triples con un PUT
# sobre TDB2 tardaba mas de 20 min, borrar el dataset es instantaneo
try:
    pedir(f"{cfg.FUSEKI}/$/datasets/{cfg.DATASET}", metodo="DELETE")
    print("dataset anterior borrado")
except urllib.error.HTTPError as e:
    if e.code != 404:
        raise
pedir(f"{cfg.FUSEKI}/$/datasets",
      urllib.parse.urlencode({"dbName": cfg.DATASET, "dbType": "tdb2"}).encode(),
      "POST", "application/x-www-form-urlencoded")
print("dataset creado:", cfg.DATASET)

for nombre in ["ontology.ttl", "instances.ttl"]:
    ruta = f"{const.RDF_DIR}/{nombre}"
    t0 = time.time()
    with open(ruta, "rb") as f:
        pedir(cfg.DATA + "?default", f, "POST", "text/turtle", largo=os.path.getsize(ruta))
    print(f"{nombre} cargado en {time.time() - t0:.0f} s")

total = contar("SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }")
canciones = contar("SELECT (COUNT(?c) AS ?n) WHERE { ?c a <%sCancion> }" % const.ONT)
print(f"Fuseki ({cfg.QUERY}): {total} triples, {canciones} canciones")
assert canciones == 100_000
