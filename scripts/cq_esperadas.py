"""Respuestas esperadas de las 8 CQ, medidas sobre los CSV de la etapa 1 (+ DuckDB para relaciones)."""
from collections import deque

import duckdb
import pandas as pd

import const

P = const.PROCESSED
songs = pd.read_csv(f"{P}/songs_final.csv", dtype=str)
for c in ["anio", "bpm", "danceability"]:
    songs[c] = pd.to_numeric(songs[c])
artists = pd.read_csv(f"{P}/artists.csv", dtype=str)
labels = pd.read_csv(f"{P}/labels.csv", dtype=str)
# "[no label]" es un sello especial de MB que significa autoedicion, no un sello real
labels = labels[labels.nombre != "[no label]"]

con = duckdb.connect(const.DUCKDB, read_only=True)
vocab = {g for (g,) in con.sql("SELECT lower(name) FROM genre").fetchall()}

# tags de artista -> generos: solo los que estan en el vocabulario de generos de MB
gen = artists[["mbid_canonico", "tags"]].dropna()
gen = gen.assign(genero=gen.tags.str.lower().str.split(";")).explode("genero")
gen = gen[gen.genero.isin(vocab)][["mbid_canonico", "genero"]].drop_duplicates()
print(f"tags de artista que son genero MB: {gen.genero.nunique()} generos, "
      f"{gen.mbid_canonico.nunique()} artistas")

# cancion -> artista canonico (los MBID del MSD pueden estar redirigidos)
canon = dict(zip(artists.artist_mbid, artists.mbid_canonico))
songs["artista"] = songs.artist_mbid.map(canon).fillna(songs.artist_mbid)
song_label = songs.merge(labels[["release_mbid", "nombre"]], on="release_mbid")
tipo = dict(zip(artists.mbid_canonico, artists.tipo))
nombre = dict(zip(artists.mbid_canonico, artists.nombre))


def titulo(n, t):
    print(f"\n=== CQ{n}: {t}")


titulo(1, f"canciones de artistas de {const.CQ_GENERO} en {const.CQ_SELLO}, {const.CQ_ANIOS}")
a, b = const.CQ_ANIOS
r = song_label[(song_label.nombre == const.CQ_SELLO) & song_label.anio.between(a, b)]
r = r[r.artista.isin(gen[gen.genero == const.CQ_GENERO].mbid_canonico)].drop_duplicates("track_id")
print(len(r), "canciones")
print(r[["title", "artist_name", "anio"]].sort_values("anio").head(5).to_string(index=False))

titulo(2, f"canciones en modo menor, > {const.CQ_BPM_MIN} bpm, de grupos (incl. orquesta y coro)")
r = songs[(songs.key_scale == "minor") & (songs.bpm > const.CQ_BPM_MIN)
          & songs.artista.map(tipo).isin(["Group", "Orchestra", "Choir"])]
print(len(r), "canciones")

# aristas 'member of band' con los dos extremos en nuestros artistas
miembros = con.sql("""
    SELECT a0.gid::varchar AS persona, a1.gid::varchar AS grupo
    FROM l_artist_artist l
    JOIN link k ON k.id = l.link JOIN link_type lt ON lt.id = k.link_type
    JOIN artist a0 ON a0.id = l.entity0 JOIN artist a1 ON a1.id = l.entity1
    WHERE lt.name = 'member of band'
""").df()
nuestros = set(artists.mbid_canonico)
miembros = miembros[miembros.persona.isin(nuestros) & miembros.grupo.isin(nuestros)].drop_duplicates()

titulo(3, "artistas del dataset que son miembros de grupos del dataset")
print(len(miembros), "pares miembroDe;", miembros.persona.nunique(), "miembros;",
      miembros.grupo.nunique(), "grupos")
top = miembros.grupo.value_counts().head(5)
print("grupos con mas miembros:", [(nombre[g], n) for g, n in top.items()])

# grupos unidos por un miembro compartido: (^miembroDe/miembroDe)+ en SPARQL
vecinos = {}
for _, gs in miembros.groupby("persona").grupo:
    for g in gs:
        vecinos.setdefault(g, set()).update(gs)
origen = artists[artists.nombre == const.CQ_GRUPO].mbid_canonico.iloc[0]
vistos, cola = {origen}, deque([origen])
while cola:
    for v in vecinos.get(cola.popleft(), ()):
        if v not in vistos:
            vistos.add(v)
            cola.append(v)
titulo(4, f"grupos conectados con {nombre[origen]} por miembros compartidos, directa o indirectamente")
print(len(vistos - {origen}), "grupos; directos:", len(vecinos.get(origen, set()) - {origen}))
print(sorted(nombre[g] for g in vecinos.get(origen, set()) - {origen})[:10])

titulo(5, f"sellos con los que ha publicado {nombre[origen]} (cancion->grabacion->lanzamiento->sello)")
r = song_label[song_label.artista == origen].nombre
print(r.nunique(), "sellos:", sorted(r.unique())[:10])

titulo(6, f"tempo y danceability medios por genero, top {const.CQ_TOP} por n de canciones")
r = songs.dropna(subset=["bpm"]).merge(gen, left_on="artista", right_on="mbid_canonico")
r = r.groupby("genero").agg(n=("track_id", "nunique"), bpm=("bpm", "mean"), dance=("danceability", "mean"))
print(r.sort_values("n", ascending=False).head(const.CQ_TOP).round(2).to_string())

titulo(7, "canciones por decada y tipo de artista")
r = songs.dropna(subset=["anio"]).assign(decada=lambda d: (d.anio // 10 * 10).astype(int),
                                          tipo=lambda d: d.artista.map(tipo))
print(pd.crosstab(r.decada, r.tipo).to_string())
print("canciones con anio:", len(r))

titulo(8, f"top {const.CQ_TOP} sellos por canciones y % en modo mayor")
r = song_label.drop_duplicates(["track_id", "nombre"]).groupby("nombre").agg(
    n=("track_id", "count"), con_modo=("key_scale", "count"),
    mayor=("key_scale", lambda s: (s == "major").sum()))
r["pct_mayor"] = (100 * r.mayor / r.con_modo).round(1)
print(r.sort_values("n", ascending=False).head(const.CQ_TOP).to_string())
