"""Genera instances.ttl (solo datos) desde los CSV de la etapa 1, y artist_relations.csv desde DuckDB."""
import gzip
import hashlib
import re
from decimal import Decimal

import duckdb
import pandas as pd
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD
from unidecode import unidecode

import const

P = const.PROCESSED
S = Namespace(const.ONT)
B = const.BASE
nsm = Graph(bind_namespaces="core").namespace_manager
nsm.bind("sem", S)
pref = {k: Namespace(B + k + "/") for k in
        ["cancion", "grabacion", "artista", "lanzamiento", "sello", "genero", "features"]}
for k, ns in pref.items():
    nsm.bind(k, ns)

songs = pd.read_csv(f"{P}/songs_final.csv", dtype=str).sort_values("track_id")
artists = pd.read_csv(f"{P}/artists.csv", dtype=str).sort_values(["mbid_canonico", "artist_mbid"])
labels = pd.read_csv(f"{P}/labels.csv", dtype=str)
labels = labels[labels.nombre != "[no label]"]  # autoedicion en MB, no es un sello
feats = pd.read_csv(f"{P}/features.csv", dtype=str).sort_values("track_id")
feats = feats.dropna(subset=["recording_mbid"]).drop_duplicates("recording_mbid")

con = duckdb.connect(const.DUCKDB, read_only=True)
vocab = {g for (g,) in con.sql("SELECT lower(name) FROM genre").fetchall()}
recs = songs.recording_mbid.dropna().drop_duplicates().to_frame()
largo = dict(con.sql("""SELECT r.gid::varchar, r.length FROM recording r
                        JOIN recs ON recs.recording_mbid = r.gid::varchar
                        WHERE r.length IS NOT NULL""").fetchall())

# miembroDe: l_artist_artist "member of band", con el tipo del "grupo" para filtrar
rel = con.sql("""
    SELECT a0.gid::varchar AS persona, a1.gid::varchar AS grupo, t1.name AS tipo_grupo
    FROM l_artist_artist l
    JOIN link k ON k.id = l.link JOIN link_type lt ON lt.id = k.link_type
    JOIN artist a0 ON a0.id = l.entity0 JOIN artist a1 ON a1.id = l.entity1
    LEFT JOIN artist_type t1 ON t1.id = a1.type
    WHERE lt.name = 'member of band'
""").df()
nuestros = set(artists.mbid_canonico)
rel = rel[rel.persona.isin(nuestros) & rel.grupo.isin(nuestros)].drop_duplicates(["persona", "grupo"])
# el rango de miembroDe es Grupo y Grupo es disjunto de Persona: un "grupo" que en MB es
# persona (errores de edicion) haria inconsistente el grafo
fuera = rel.tipo_grupo == "Person"
print(f"miembroDe: {len(rel)} pares, {fuera.sum()} descartados porque el grupo es Person en MB")
rel = rel[~fuera].sort_values(["persona", "grupo"])
rel.assign(relacion="member of band", fuente="musicbrainz")[
    ["persona", "grupo", "relacion", "fuente"]].to_csv(f"{P}/artist_relations.csv", index=False)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", unidecode(s).lower()).strip("-")


generos = sorted({g for t in artists.tags.dropna() for g in t.lower().split(";") if g in vocab})
slugs = {g: slug(g) for g in generos}
assert len(set(slugs.values())) == len(slugs), "dos generos distintos dan el mismo slug"

out = f"{const.RDF_DIR}/instances.ttl"
f = open(out, "w", encoding="utf-8")
for k, ns in sorted(nsm.namespaces()):
    f.write(f"@prefix {k}: <{ns}> .\n")
n = 0


def t(s, p, o):
    global n
    f.write(f"{s.n3(nsm)} {p.n3(nsm)} {o.n3(nsm)} .\n")
    n += 1


def lit(s, p, v):
    # los nulos no generan triple
    if isinstance(v, str) and v.strip():
        t(s, p, Literal(v))  # literal simple = xsd:string en RDF 1.1


def dec(s, p, v):
    if isinstance(v, str) and v.strip():
        t(s, p, Literal(format(Decimal(v), "f"), datatype=XSD.decimal))


def anio(s, p, v):
    if isinstance(v, str) and v.strip() and int(float(v)) > 0:
        t(s, p, Literal(str(int(float(v))).zfill(4), datatype=XSD.gYear))


for g in generos:
    gi = pref["genero"][slugs[g]]
    t(gi, RDF.type, S.Genero)
    lit(gi, S.nombre, g)

clase = {"Person": S.Persona, "Group": S.Grupo, "Orchestra": S.Orquesta, "Choir": S.Coro,
         "Character": S.Personaje}
canon = dict(zip(artists.artist_mbid, artists.mbid_canonico))
for mbid, filas in artists.groupby("mbid_canonico", sort=True):
    a, r = pref["artista"][mbid], filas.iloc[0]
    t(a, RDF.type, clase.get(r.tipo, S.Artista))
    lit(a, S.artistMbid, mbid)
    for viejo in filas.artist_mbid:
        if viejo != mbid:
            lit(a, S.mbidAntiguo, viejo)
    lit(a, S.nombre, r.nombre)
    lit(a, S.sexo, r.genero)
    lit(a, S.area, r.area)
    anio(a, S.anioInicio, r.anio_inicio)
    anio(a, S.anioFin, r.anio_fin)
    if isinstance(r.wikidata, str):
        t(a, S.wikidata, URIRef(r.wikidata))
    tags = sorted({x for x in str(r.tags).lower().split(";") if x in vocab}) if isinstance(r.tags, str) else []
    for g in tags:
        t(a, S.tieneGenero, pref["genero"][slugs[g]])

# artistas del MSD que no estan en MB (983 canciones): solo lo que trae el MSD
sueltos = songs[~songs.artist_mbid.isin(canon)].drop_duplicates("artist_mbid").sort_values("artist_mbid")
for _, r in sueltos.iterrows():
    a = pref["artista"][r.artist_mbid]
    t(a, RDF.type, S.Artista)
    lit(a, S.artistMbid, r.artist_mbid)
    lit(a, S.nombre, r.artist_name)

for _, r in rel.iterrows():
    t(pref["artista"][r.persona], S.miembroDe, pref["artista"][r.grupo])

for mbid, filas in labels.sort_values(["label_mbid", "nombre"]).groupby("label_mbid", sort=True):
    se = pref["sello"][mbid]
    t(se, RDF.type, S.Sello)
    lit(se, S.labelMbid, mbid)
    lit(se, S.nombre, filas.nombre.iloc[0])

sellos = labels.drop_duplicates(["release_mbid", "label_mbid"]).sort_values(["release_mbid", "label_mbid"])
sellos = sellos.groupby("release_mbid").label_mbid.apply(list).to_dict()
lanz = songs.dropna(subset=["release_mbid"]).drop_duplicates("release_mbid").sort_values("release_mbid")
for _, r in lanz.iterrows():
    la = pref["lanzamiento"][r.release_mbid]
    t(la, RDF.type, S.Lanzamiento)
    lit(la, S.releaseMbid, r.release_mbid)
    lit(la, S.tituloLanzamiento, r.release_titulo)
    lit(la, S.pais, r.release_pais)
    lit(la, S.tipoLanzamiento, r.release_tipo)
    for se in sellos.get(r.release_mbid, []):
        t(la, S.editadoPor, pref["sello"][se])

fcols = {"averageLoudness": "average_loudness", "dynamicComplexity": "dynamic_complexity",
         "mfccZeroMean": "mfcc_zero_mean", "bpm": "bpm",
         "bpmPrimerPicoMedia": "bpm_histogram_first_peak_bpm_mean",
         "bpmPrimerPicoMediana": "bpm_histogram_first_peak_bpm_median",
         "bpmSegundoPicoMedia": "bpm_histogram_second_peak_bpm_mean",
         "bpmSegundoPicoMediana": "bpm_histogram_second_peak_bpm_median",
         "danceability": "danceability", "onsetRate": "onset_rate",
         "frecuenciaAfinacion": "tuning_frequency",
         "desviacionTemperada": "tuning_equal_tempered_deviation"}
con_features = set(feats.recording_mbid)
for _, r in feats.sort_values("recording_mbid").iterrows():
    fe = pref["features"][r.recording_mbid]
    t(fe, RDF.type, S.FeaturesAcusticas)
    for p, c in fcols.items():
        dec(fe, S[p], r[c])
    lit(fe, S.tonalidad, r.key_key)
    lit(fe, S.modo, r.key_scale)

grab = songs.dropna(subset=["recording_mbid"]).drop_duplicates("recording_mbid").sort_values("recording_mbid")
for _, r in grab.iterrows():
    gr = pref["grabacion"][r.recording_mbid]
    t(gr, RDF.type, S.Grabacion)
    lit(gr, S.recordingMbid, r.recording_mbid)
    if r.recording_mbid in largo:
        dec(gr, S.duracionMs, str(largo[r.recording_mbid]))
    if isinstance(r.release_mbid, str):
        t(gr, S.publicadaEn, pref["lanzamiento"][r.release_mbid])
    if r.recording_mbid in con_features:
        t(gr, S.descritaPor, pref["features"][r.recording_mbid])

for _, r in songs.iterrows():
    c = pref["cancion"][r.track_id]
    t(c, RDF.type, S.Cancion)
    lit(c, S.trackId, r.track_id)
    lit(c, S.titulo, r.title)
    lit(c, S.releaseMsd, r.release)
    dec(c, S.duracion, r.duration)
    anio(c, S.anio, r.anio)
    if isinstance(r.anio, str):
        lit(c, S.fuenteAnio, r.fuente_anio)
    lit(c, S.metodoMatch, r.metodo_match)
    t(c, S.interpretadaPor, pref["artista"][canon.get(r.artist_mbid, r.artist_mbid)])
    if isinstance(r.recording_mbid, str):
        t(c, S.correspondeA, pref["grabacion"][r.recording_mbid])

f.close()
datos = open(out, "rb").read()
sha = hashlib.sha256(datos).hexdigest()
# el .ttl pasa de 100 MB (limite de GitHub): al repo va comprimido. mtime=0 para que el
# .gz tambien salga identico en cada ejecucion
with open(out + ".gz", "wb") as fz, gzip.GzipFile(fileobj=fz, mode="wb", mtime=0, filename="") as z:
    z.write(datos)
print(f"generos {len(generos)}, artistas {artists.mbid_canonico.nunique()} + {len(sueltos)} sin MB, "
      f"sellos {labels.label_mbid.nunique()}, lanzamientos {len(lanz)}, features {len(feats)}, "
      f"grabaciones {len(grab)} ({len(largo)} con duracion), canciones {len(songs)}")
print(f"{out}: {n} triples, sha256 {sha}")
