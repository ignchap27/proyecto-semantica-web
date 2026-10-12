"""Genera ontology.ttl: solo vocabulario (clases, propiedades y axiomas OWL), nada de datos."""
from collections import Counter

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, XSD

import const

S = Namespace(const.ONT)
g = Graph()
g.bind("sem", S)
g.bind("owl", OWL)

ont = URIRef(const.ONT.rstrip("#"))
g.add((ont, RDF.type, OWL.Ontology))
g.add((ont, RDFS.label, Literal("Explorador musical del MSD (grupo 5)", lang="es")))

clases = {
    "Cancion": "Canción", "Grabacion": "Grabación", "Lanzamiento": "Lanzamiento",
    "Sello": "Sello", "Artista": "Artista", "Persona": "Persona", "Grupo": "Grupo",
    "Orquesta": "Orquesta", "Coro": "Coro", "Personaje": "Personaje", "Genero": "Género",
    "FeaturesAcusticas": "Features acústicas", "GrabacionAnalizada": "Grabación analizada",
}
for c, label in clases.items():
    g.add((S[c], RDF.type, OWL.Class))
    g.add((S[c], RDFS.label, Literal(label, lang="es")))

for sub, sup in [("Persona", "Artista"), ("Grupo", "Artista"), ("Personaje", "Artista"),
                 ("Orquesta", "Grupo"), ("Coro", "Grupo"), ("GrabacionAnalizada", "Grabacion")]:
    g.add((S[sub], RDFS.subClassOf, S[sup]))

objeto = [
    ("interpretadaPor", "Cancion", "Artista", "interpretada por"),
    ("correspondeA", "Cancion", "Grabacion", "se corresponde con"),
    ("publicadaEn", "Grabacion", "Lanzamiento", "publicada en"),
    ("editadoPor", "Lanzamiento", "Sello", "editado por"),
    ("descritaPor", "Grabacion", "FeaturesAcusticas", "descrita por"),
    ("tieneGenero", "Artista", "Genero", "tiene género"),
    ("miembroDe", "Artista", "Grupo", "miembro de"),
    ("tieneMiembro", "Grupo", "Artista", "tiene miembro"),
]
for p, d, r, label in objeto:
    g.add((S[p], RDF.type, OWL.ObjectProperty))
    g.add((S[p], RDFS.label, Literal(label, lang="es")))
    g.add((S[p], RDFS.domain, S[d]))
    g.add((S[p], RDFS.range, S[r]))

# (propiedad, dominio, rango); el label es el nombre de la columna de origen
D = XSD.decimal
datos = [
    ("trackId", "Cancion", XSD.string, "track_id"),
    ("titulo", "Cancion", XSD.string, "title"),
    ("releaseMsd", "Cancion", XSD.string, "release"),
    ("duracion", "Cancion", D, "duration (segundos)"),
    ("anio", "Cancion", XSD.gYear, "anio"),
    ("fuenteAnio", "Cancion", XSD.string, "fuente_anio"),
    ("metodoMatch", "Cancion", XSD.string, "metodo_match"),
    ("recordingMbid", "Grabacion", XSD.string, "recording_mbid"),
    ("duracionMs", "Grabacion", D, "recording.length (milisegundos)"),
    ("nombre", None, XSD.string, "nombre"),  # artista, sello y genero: sin dominio
    ("artistMbid", "Artista", XSD.string, "mbid_canonico"),
    ("mbidAntiguo", "Artista", XSD.string, "artist_mbid (antes de resolver el redirect)"),
    ("sexo", "Artista", XSD.string, "artista_genero"),
    ("area", "Artista", XSD.string, "artista_area"),
    ("anioInicio", "Artista", XSD.gYear, "artista_anio_inicio"),
    ("anioFin", "Artista", XSD.gYear, "artista_anio_fin"),
    ("releaseMbid", "Lanzamiento", XSD.string, "release_mbid"),
    ("tituloLanzamiento", "Lanzamiento", XSD.string, "release_titulo"),
    ("pais", "Lanzamiento", XSD.string, "release_pais"),
    ("tipoLanzamiento", "Lanzamiento", XSD.string, "release_tipo"),
    ("labelMbid", "Sello", XSD.string, "label_mbid"),
    ("averageLoudness", "FeaturesAcusticas", D, "average_loudness"),
    ("dynamicComplexity", "FeaturesAcusticas", D, "dynamic_complexity"),
    ("mfccZeroMean", "FeaturesAcusticas", D, "mfcc_zero_mean"),
    ("bpm", "FeaturesAcusticas", D, "bpm"),
    ("bpmPrimerPicoMedia", "FeaturesAcusticas", D, "bpm_histogram_first_peak_bpm_mean"),
    ("bpmPrimerPicoMediana", "FeaturesAcusticas", D, "bpm_histogram_first_peak_bpm_median"),
    ("bpmSegundoPicoMedia", "FeaturesAcusticas", D, "bpm_histogram_second_peak_bpm_mean"),
    ("bpmSegundoPicoMediana", "FeaturesAcusticas", D, "bpm_histogram_second_peak_bpm_median"),
    ("danceability", "FeaturesAcusticas", D, "danceability"),
    ("onsetRate", "FeaturesAcusticas", D, "onset_rate"),
    ("tonalidad", "FeaturesAcusticas", XSD.string, "key_key"),
    ("modo", "FeaturesAcusticas", XSD.string, "key_scale"),
    ("frecuenciaAfinacion", "FeaturesAcusticas", D, "tuning_frequency"),
    ("desviacionTemperada", "FeaturesAcusticas", D, "tuning_equal_tempered_deviation"),
]
for p, d, r, label in datos:
    g.add((S[p], RDF.type, OWL.DatatypeProperty))
    g.add((S[p], RDFS.label, Literal(label, lang="es")))
    if d:
        g.add((S[p], RDFS.domain, S[d]))
    g.add((S[p], RDFS.range, r))

# wikidata enlaza fuera: propiedad de objeto hacia un recurso cualquiera
g.add((S.wikidata, RDF.type, OWL.ObjectProperty))
g.add((S.wikidata, RDFS.label, Literal("artista_wikidata", lang="es")))
g.add((S.wikidata, RDFS.domain, S.Artista))


def lista(*xs):
    n = BNode()
    Collection(g, n, list(xs))
    return n


# --- axiomas OWL (justificados en el informe de la Etapa 2) ---
# 1
d = BNode()
g.add((d, RDF.type, OWL.AllDisjointClasses))
g.add((d, OWL.members, lista(*(S[c] for c in ["Cancion", "Grabacion", "Lanzamiento", "Sello",
                                               "Artista", "Genero", "FeaturesAcusticas"]))))
# 2
g.add((S.Persona, OWL.disjointWith, S.Grupo))
# 3-5: duraciones en unidades distintas, cada una funcional por separado
for p in ["duracion", "duracionMs", "correspondeA"]:
    g.add((S[p], RDF.type, OWL.FunctionalProperty))
# 6-7: el MBID identifica grabacion y artista. Nunca sobre Cancion: varias filas del MSD
# comparten grabacion y el razonador las fusionaria.
# No owl:hasKey: owlrl 7 tiene un bug con claves de una sola propiedad y declara sameAs
# entre todas las instancias de la clase
for p in ["recordingMbid", "artistMbid"]:
    g.add((S[p], RDF.type, OWL.InverseFunctionalProperty))
# 8
g.add((S.tieneMiembro, OWL.inverseOf, S.miembroDe))
# 9
r = BNode()
g.add((r, RDF.type, OWL.Restriction))
g.add((r, OWL.onProperty, S.descritaPor))
g.add((r, OWL.someValuesFrom, S.FeaturesAcusticas))
e = BNode()
g.add((e, RDF.type, OWL.Class))
g.add((e, OWL.intersectionOf, lista(S.Grabacion, r)))
g.add((S.GrabacionAnalizada, OWL.equivalentClass, e))

out = f"{const.RDF_DIR}/ontology.ttl"
g.serialize(out, format="turtle")

g2 = Graph().parse(out)
assert len(g2) == len(g), "el ttl no da el mismo grafo al releerlo"
tipos = Counter()
for p in [OWL.disjointWith, OWL.inverseOf, OWL.equivalentClass]:
    tipos[p.fragment] += len(list(g2.subject_objects(p)))
tipos["AllDisjointClasses"] = len(list(g2.subjects(RDF.type, OWL.AllDisjointClasses)))
for t in [OWL.FunctionalProperty, OWL.InverseFunctionalProperty]:
    tipos[t.fragment] = len(list(g2.subjects(RDF.type, t)))
print(f"{out}: {len(g2)} triples, {len(clases)} clases, "
      f"{len(objeto) + 1} prop. de objeto, {len(datos)} prop. de dato")
print(f"axiomas OWL: {sum(tipos.values())} de {len(tipos)} tipos -> {dict(tipos)}")
assert sum(tipos.values()) >= 8 and len(tipos) >= 3 and tipos["equivalentClass"] >= 1
