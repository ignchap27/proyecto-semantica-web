"""Valida ontology.ttl + instances.ttl: parsean, los conteos cuadran con los CSV y owlrl dice consistente."""
import time
from collections import Counter

import owlrl
import pandas as pd
from owlrl.Namespaces import ERRNS
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF

import const

P = const.PROCESSED
S = Namespace(const.ONT)


def razonar(g):
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
    return [str(m) for m in g.objects(None, ERRNS.error)]


t0 = time.time()
ont = Graph().parse(f"{const.RDF_DIR}/ontology.ttl")
ins = Graph().parse(f"{const.RDF_DIR}/instances.ttl")
print(f"parsean: ontologia {len(ont)} triples, instancias {len(ins)} triples ({time.time() - t0:.0f} s)")

# nunca mezclados: las instancias no definen clases ni propiedades
assert not set(ins.subjects(RDF.type, OWL.Class)) and not set(ins.subjects(RDF.type, OWL.ObjectProperty))

tipos = Counter(o for o in ins.objects(None, RDF.type))
print({o.split("#")[-1]: n for o, n in sorted(tipos.items())})

songs = pd.read_csv(f"{P}/songs_final.csv", dtype=str)
artists = pd.read_csv(f"{P}/artists.csv", dtype=str)
esperado = {
    S.Cancion: len(songs),
    S.Grabacion: songs.recording_mbid.nunique(),
    S.Lanzamiento: songs.release_mbid.nunique(),
    S.FeaturesAcusticas: pd.read_csv(f"{P}/features.csv", dtype=str).recording_mbid.nunique(),
}
for c, n in esperado.items():
    assert tipos[c] == n, f"{c}: {tipos[c]} en el grafo, {n} en los CSV"
assert tipos[S.Cancion] == 100_000
artistas = sum(tipos[S[c]] for c in ["Artista", "Persona", "Grupo", "Orquesta", "Coro", "Personaje"])
canon = set(artists.mbid_canonico)
fuera = songs[~songs.artist_mbid.isin(artists.artist_mbid)].artist_mbid.nunique()
assert artistas == len(canon) + fuera, f"artistas {artistas} != {len(canon)} + {fuera}"
print(f"conteos cuadran con los CSV: {tipos[S.Cancion]} canciones, {artistas} artistas")

# ninguna entidad con dos IRI que solo difieran en mayusculas o espacios
# toda entidad tiene rdf:type; ins.subjects() sin indice tardaba ~12 min
iris = set(ins.subjects(RDF.type))
claves = Counter(str(i).lower().replace(" ", "") for i in iris)
dobles = [k for k, n in claves.items() if n > 1]
assert not dobles and not any(" " in i for i in iris), dobles[:5]
print(f"{len(iris)} IRI de sujeto, ninguna duplicada por mayusculas o espacios")

# razonador: ontologia + las primeras N canciones y todo lo alcanzable a 3 saltos
semilla = sorted(ins.subjects(RDF.type, S.Cancion))[:const.MUESTRA_RAZONADOR]
nodos, frente = set(semilla), set(semilla)
for _ in range(3):
    frente = {o for s in frente for o in ins.objects(s) if isinstance(o, URIRef)} - nodos
    nodos |= frente
muestra = Graph()
for n in nodos:
    for p, o in ins.predicate_objects(n):
        muestra.add((n, p, o))
g = ont + muestra
n0 = len(g)
t0 = time.time()
errores = razonar(g)
print(f"muestra: {len(semilla)} canciones, {len(muestra)} triples; owlrl {n0} -> {len(g)} "
      f"triples en {time.time() - t0:.0f} s")
for e in errores[:10]:
    print("  ERROR:", e)

canciones = set(g.subjects(RDF.type, S.Cancion))
fusionadas = [(a, b) for a, b in g.subject_objects(OWL.sameAs) if a != b and a in canciones]
analizadas = len(set(g.subjects(RDF.type, S.GrabacionAnalizada)))
print(f"owl:sameAs entre canciones distintas: {len(fusionadas)}; grabaciones clasificadas "
      f"como GrabacionAnalizada: {analizadas}; artistas deducidos: {len(set(g.subjects(RDF.type, S.Artista)))}")
assert not fusionadas

# control: el razonador si detecta una contradiccion cuando la hay
malo = ont + Graph()
x = URIRef(const.BASE + "artista/prueba")
malo.add((x, RDF.type, S.Persona))
malo.add((x, RDF.type, S.Grupo))
assert razonar(malo), "owlrl no detecto Persona y Grupo a la vez"
print("control: owlrl detecta un artista Persona y Grupo a la vez")
# owlrl no marca dos literales distintos en una propiedad funcional de dato;
# por eso la funcionalidad de las duraciones se comprueba aqui, sobre el grafo completo
for p in [S.duracion, S.duracionMs]:
    c = Counter(s for s in ins.subjects(p))
    assert max(c.values()) == 1, f"{p} con dos valores"
print("duracion y duracionMs: un solo valor por entidad en todo el grafo")

# control de la trampa: dos canciones con la misma grabacion no se fusionan; dos
# grabaciones con el mismo MBID si
c1, c2 = URIRef(const.BASE + "cancion/A"), URIRef(const.BASE + "cancion/B")
g1, g2 = URIRef(const.BASE + "grabacion/x1"), URIRef(const.BASE + "grabacion/x2")
prueba = ont + Graph()
for c in (c1, c2):
    prueba.add((c, RDF.type, S.Cancion))
    prueba.add((c, S.correspondeA, g1))
for gr in (g1, g2):
    prueba.add((gr, S.recordingMbid, Literal("x")))
assert not razonar(prueba)
assert (c1, OWL.sameAs, c2) not in prueba and (g1, OWL.sameAs, g2) in prueba
print("control: canciones con la misma grabacion siguen separadas; grabaciones con el mismo MBID se fusionan")

assert not errores
print("CONSISTENTE")
