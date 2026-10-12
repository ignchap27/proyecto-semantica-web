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
g.add((ont, RDFS.comment, Literal(
    "Vocabulario para describir 100.000 canciones del Million Song Dataset enriquecidas con "
    "MusicBrainz y AcousticBrainz: quién las interpreta, en qué discos salieron, con qué sello "
    "y cómo suenan.", lang="es")))


def describir(x, label, comment):
    g.add((x, RDFS.label, Literal(label, lang="es")))
    g.add((x, RDFS.comment, Literal(comment, lang="es")))


clases = {
    "Cancion": ("Canción", "Una fila del Million Song Dataset (un track_id). Varias canciones "
                "pueden ser la misma grabación."),
    "Grabacion": ("Grabación", "Una grabación de MusicBrainz (recording): un audio concreto, "
                  "identificado por su MBID, que puede salir en varios discos."),
    "Lanzamiento": ("Lanzamiento", "Un disco o edición publicada (release de MusicBrainz): "
                    "álbum, sencillo, recopilatorio, reedición..."),
    "Sello": ("Sello", "Sello discográfico que edita un lanzamiento. La autoedición "
              "('[no label]' en MusicBrainz) no cuenta como sello."),
    "Artista": ("Artista", "Quien interpreta las canciones: una persona, un grupo u otro tipo "
                "de artista de MusicBrainz."),
    "Persona": ("Persona", "Artista que es una sola persona (solista)."),
    "Grupo": ("Grupo", "Artista formado por varias personas (banda, dúo...)."),
    "Orquesta": ("Orquesta", "Grupo que es una orquesta."),
    "Coro": ("Coro", "Grupo que es un coro."),
    "Personaje": ("Personaje", "Artista ficticio, por ejemplo un personaje de dibujos animados "
                  "al que se le atribuyen canciones."),
    "Genero": ("Género", "Género musical. Sale de las etiquetas del artista que están en el "
               "vocabulario oficial de géneros de MusicBrainz."),
    "FeaturesAcusticas": ("Features acústicas", "Medidas del audio de una grabación calculadas "
                          "por AcousticBrainz: tempo, volumen, tonalidad, bailabilidad..."),
    "GrabacionAnalizada": ("Grabación analizada", "Clase definida: toda grabación que tiene "
                           "features acústicas de AcousticBrainz."),
}
for c, (label, comment) in clases.items():
    g.add((S[c], RDF.type, OWL.Class))
    describir(S[c], label, comment)

for sub, sup in [("Persona", "Artista"), ("Grupo", "Artista"), ("Personaje", "Artista"),
                 ("Orquesta", "Grupo"), ("Coro", "Grupo"), ("GrabacionAnalizada", "Grabacion")]:
    g.add((S[sub], RDFS.subClassOf, S[sup]))

objeto = [
    ("interpretadaPor", "Cancion", "Artista", "interpretada por",
     "Une la canción con el artista que la interpreta."),
    ("correspondeA", "Cancion", "Grabacion", "se corresponde con",
     "Une la canción del MSD con su grabación en MusicBrainz (resultado del matching). "
     "Como mucho una por canción."),
    ("publicadaEn", "Grabacion", "Lanzamiento", "publicada en",
     "Disco en el que salió la grabación. Una grabación puede salir en varios."),
    ("editadoPor", "Lanzamiento", "Sello", "editado por",
     "Sello discográfico que publicó el lanzamiento."),
    ("descritaPor", "Grabacion", "FeaturesAcusticas", "descrita por",
     "Une la grabación con sus medidas de audio de AcousticBrainz."),
    ("tieneGenero", "Artista", "Genero", "tiene género",
     "Género musical asociado al artista."),
    ("miembroDe", "Artista", "Grupo", "miembro de",
     "El artista forma o formó parte del grupo (relación 'member of band' de MusicBrainz)."),
    ("tieneMiembro", "Grupo", "Artista", "tiene miembro",
     "Inversa de 'miembro de': el grupo tiene a ese artista entre sus miembros."),
]
for p, d, r, label, comment in objeto:
    g.add((S[p], RDF.type, OWL.ObjectProperty))
    describir(S[p], label, comment)
    g.add((S[p], RDFS.domain, S[d]))
    g.add((S[p], RDFS.range, S[r]))

# (propiedad, dominio, rango, label, comment); el comment dice la columna de origen
D = XSD.decimal
datos = [
    ("trackId", "Cancion", XSD.string, "identificador MSD",
     "Identificador de la canción en el Million Song Dataset (columna track_id)."),
    ("titulo", "Cancion", XSD.string, "título", "Título de la canción según el MSD (title)."),
    ("releaseMsd", "Cancion", XSD.string, "disco según el MSD",
     "Nombre del disco tal como viene en el MSD (release), sin reconciliar."),
    ("duracion", "Cancion", D, "duración (s)", "Duración de la canción en segundos (duration del MSD)."),
    ("anio", "Cancion", XSD.gYear, "año",
     "Año de publicación consolidado: el del MSD o, si falta, el de MusicBrainz (anio)."),
    ("fuenteAnio", "Cancion", XSD.string, "fuente del año",
     "De dónde salió el año: 'msd' o 'musicbrainz' (fuente_anio)."),
    ("metodoMatch", "Cancion", XSD.string, "método de matching",
     "Cómo se encontró la grabación: 'exacto', 'sin_sufijo' o 'fuzzy' (metodo_match)."),
    ("recordingMbid", "Grabacion", XSD.string, "MBID de la grabación",
     "Identificador de la grabación en MusicBrainz (recording_mbid). Identifica una sola grabación."),
    ("duracionMs", "Grabacion", D, "duración (ms)",
     "Duración de la grabación en milisegundos según MusicBrainz (recording.length)."),
    ("nombre", None, XSD.string, "nombre",  # artista, sello y genero: sin dominio
     "Nombre de un artista, sello o género."),
    ("artistMbid", "Artista", XSD.string, "MBID del artista",
     "Identificador actual del artista en MusicBrainz (mbid_canonico). Identifica un solo artista."),
    ("mbidAntiguo", "Artista", XSD.string, "MBID antiguo",
     "Identificador que traía el MSD cuando el artista se fusionó después con otro en "
     "MusicBrainz (artist_mbid antes de resolver la redirección)."),
    ("sexo", "Artista", XSD.string, "sexo",
     "Sexo del artista si es persona: Male, Female... (artista_genero)."),
    ("area", "Artista", XSD.string, "área", "País o zona de origen del artista (artista_area)."),
    ("anioInicio", "Artista", XSD.gYear, "año de inicio",
     "Año de nacimiento o de formación del grupo (artista_anio_inicio)."),
    ("anioFin", "Artista", XSD.gYear, "año de fin",
     "Año de muerte o de disolución del grupo (artista_anio_fin)."),
    ("releaseMbid", "Lanzamiento", XSD.string, "MBID del lanzamiento",
     "Identificador del lanzamiento en MusicBrainz (release_mbid)."),
    ("tituloLanzamiento", "Lanzamiento", XSD.string, "título del lanzamiento",
     "Título del disco según MusicBrainz (release_titulo)."),
    ("pais", "Lanzamiento", XSD.string, "país", "País donde se publicó el lanzamiento (release_pais)."),
    ("tipoLanzamiento", "Lanzamiento", XSD.string, "tipo de lanzamiento",
     "Tipo de disco: Album, Single, EP... (release_tipo)."),
    ("labelMbid", "Sello", XSD.string, "MBID del sello",
     "Identificador del sello en MusicBrainz (label_mbid)."),
    ("averageLoudness", "FeaturesAcusticas", D, "volumen medio",
     "Volumen medio del audio, de 0 a 1 (average_loudness)."),
    ("dynamicComplexity", "FeaturesAcusticas", D, "complejidad dinámica",
     "Cuánto varía el volumen a lo largo de la pista (dynamic_complexity)."),
    ("mfccZeroMean", "FeaturesAcusticas", D, "media del MFCC 0",
     "Media del primer coeficiente MFCC, relacionado con la energía del sonido (mfcc_zero_mean)."),
    ("bpm", "FeaturesAcusticas", D, "tempo (BPM)", "Tempo en pulsos por minuto (bpm)."),
    ("bpmPrimerPicoMedia", "FeaturesAcusticas", D, "BPM del primer pico (media)",
     "Media del tempo más frecuente en el histograma de BPM (bpm_histogram_first_peak_bpm_mean)."),
    ("bpmPrimerPicoMediana", "FeaturesAcusticas", D, "BPM del primer pico (mediana)",
     "Mediana del tempo más frecuente en el histograma de BPM (bpm_histogram_first_peak_bpm_median)."),
    ("bpmSegundoPicoMedia", "FeaturesAcusticas", D, "BPM del segundo pico (media)",
     "Media del segundo tempo más frecuente (bpm_histogram_second_peak_bpm_mean)."),
    ("bpmSegundoPicoMediana", "FeaturesAcusticas", D, "BPM del segundo pico (mediana)",
     "Mediana del segundo tempo más frecuente (bpm_histogram_second_peak_bpm_median)."),
    ("danceability", "FeaturesAcusticas", D, "bailabilidad",
     "Qué tan bailable es la pista; más alto, más bailable (danceability)."),
    ("onsetRate", "FeaturesAcusticas", D, "tasa de ataques",
     "Notas o golpes que empiezan por segundo (onset_rate)."),
    ("tonalidad", "FeaturesAcusticas", XSD.string, "tonalidad", "Nota de la tonalidad: C, F#... (key_key)."),
    ("modo", "FeaturesAcusticas", XSD.string, "modo", "Modo de la tonalidad: major o minor (key_scale)."),
    ("frecuenciaAfinacion", "FeaturesAcusticas", D, "frecuencia de afinación",
     "Frecuencia de referencia de la afinación en Hz, normalmente cerca de 440 (tuning_frequency)."),
    ("desviacionTemperada", "FeaturesAcusticas", D, "desviación temperada",
     "Cuánto se aparta la afinación del temperamento igual (tuning_equal_tempered_deviation)."),
]
for p, d, r, label, comment in datos:
    g.add((S[p], RDF.type, OWL.DatatypeProperty))
    describir(S[p], label, comment)
    if d:
        g.add((S[p], RDFS.domain, S[d]))
    g.add((S[p], RDFS.range, r))

# wikidata enlaza fuera: propiedad de objeto hacia un recurso cualquiera
g.add((S.wikidata, RDF.type, OWL.ObjectProperty))
describir(S.wikidata, "página en Wikidata",
          "Enlace a la ficha del artista en Wikidata, sacado de las URL de MusicBrainz (artista_wikidata).")
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
sin = [x for x in g2.subjects(RDF.type, None) if isinstance(x, URIRef)
       and (g2.value(x, RDFS.label) is None or g2.value(x, RDFS.comment) is None)]
assert not sin, f"sin label o comment: {sin}"
print(f"{out}: {len(g2)} triples, {len(clases)} clases, "
      f"{len(objeto) + 1} prop. de objeto, {len(datos)} prop. de dato")
print(f"axiomas OWL: {sum(tipos.values())} de {len(tipos)} tipos -> {dict(tipos)}")
assert sum(tipos.values()) >= 8 and len(tipos) >= 3 and tipos["equivalentClass"] >= 1
