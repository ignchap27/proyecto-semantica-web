# Informe Etapa 2 — De los datos consolidados a la ontología

Ignacio Chaparro

> Máximo 6 páginas. Las secciones se llenan fase a fase.

## 1. Producto y competency questions

Construimos la ontología pensando en un **explorador musical** del catálogo del MSD:
filtrar canciones por sello, género y época, saltar de un artista a sus miembros y a
los grupos con los que comparte gente, y comparar el perfil acústico entre géneros y
sellos. Las competency questions (CQ, preguntas que la ontología tiene que poder
responder) salen de ahí y se escribieron antes de tocar el modelo, para revisarlo.

Las respuestas esperadas se midieron sobre los CSV de la Etapa 1 (`make cq`).
"Género" es un tag del artista que está en el vocabulario oficial de géneros de
MusicBrainz.

| # | Pregunta | Tipo | Respuesta esperada |
|---|---|---|---|
| 1 | Canciones de artistas de rock publicadas por Columbia entre 1970 y 1979 | Recuperación | 79 |
| 2 | Canciones en modo menor y > 140 bpm de grupos (incluidas orquestas y coros) | Recuperación | 2.849 |
| 3 | Artistas del dataset que son miembros de grupos del dataset, y de cuál | Navegación | 2.764 pares |
| 4 | Grupos conectados con Deep Purple por miembros compartidos, directa o indirectamente | Navegación | 219 grupos |
| 5 | Sellos con los que ha publicado Deep Purple | Navegación | 12 |
| 6 | Tempo y bailabilidad medios por género (top 10) | Agregación | rock 125,2 bpm; hip hop 106,7 bpm y el más bailable |
| 7 | Canciones por década y tipo de artista | Agregación | 78.897 con año |
| 8 | Top 10 sellos por canciones y % en modo mayor | Agregación | Columbia 1.537 (67,3 %) |

El SPARQL de cada una está en `docs/competency_questions.md`.

## 2. Cambios respecto al modelo de la Etapa 1

Pasamos cada CQ por el modelo de la Etapa 1 y salieron tres listas.

**Lo que ya tenía y se usa:** las seis clases y la cadena canción → grabación →
lanzamiento → sello, que sostiene las CQ 1, 5 y 8; además año, tempo, bailabilidad y
modo.

**Lo que faltaba:**
- Una clase `Genero` con la relación `tieneGenero`. En la Etapa 1 los géneros eran un
  texto con `;`, y con texto no se puede agrupar ni cruzar (CQ 1 y 6).
- Subclases de `Artista`: `Persona` y `Grupo`, y `Orquesta` y `Coro` bajo `Grupo`. Antes
  era un texto `tipoArtista`; con clases, la CQ 2 encuentra orquestas al pedir grupos y
  la CQ 7 recorre la jerarquía.
- La relación `miembroDe` entre artistas, que viene de `l_artist_artist` en MusicBrainz
  (CQ 3 y 4). Hay que exportarla a un CSV nuevo con su procedencia.
- Dos duraciones separadas (canción en segundos, grabación en milisegundos) y el MBID
  antiguo de los artistas fusionados.

**Lo que sobraba:** los textos de tags y de tipo de artista (los reemplazan las clases y
`tieneGenero`), `anioMsd` (el 0 del MSD era un nulo; `anio` + `fuenteAnio` lo cubren) y
`metodoMatch`, que pasa de `Grabacion` a `Cancion` porque describe el emparejamiento de
cada fila del MSD. Los descriptores acústicos que ninguna CQ usa se mantienen: son la
parte del dataset que aporta AcousticBrainz.

**Lo que no está en los datos:** no hay jerarquía de géneros (no se extrajo
`l_genre_genre`) y las colaboraciones entre nuestros artistas son solo 83, así que no
hay CQ sobre ninguna de las dos.

## 3. Ontología: construcciones RDFS y OWL

_Fase H._

## 4. Instancias y esquema de IRI

_Fase I._

## 5. Validación y carga en Fuseki

_Fases J y K._

## 6. Problemas encontrados

- `[no label]` aparece como sello en MusicBrainz, pero significa autoedición; se excluye.
- Hay canciones con año 2020+: son reediciones que rellenaron el `year=0` del MSD.
