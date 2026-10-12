# Competency questions (Etapa 2, fase G)

Una *competency question* (CQ) es una pregunta que la ontología tiene que poder
responder. Se escriben **antes** de cerrar el modelo porque sirven para revisarlo: si una
pregunta no se puede escribir en SPARQL sobre el modelo, al modelo le falta algo.

## El producto

Un **explorador musical** sobre el catálogo del MSD: filtrar canciones por sello,
género y época; saltar de un artista a sus miembros y a los grupos con los que comparte
gente; comparar el perfil acústico (tempo, bailabilidad, modo) entre géneros y sellos.
Las ocho preguntas salen de las pantallas de ese explorador.

## Las ocho preguntas

Las respuestas esperadas se midieron con `make cq` (`scripts/cq_esperadas.py`), con pandas
sobre los CSV de la Etapa 1 y DuckDB para las relaciones entre artistas y el vocabulario
de géneros. Los parámetros (sello, género, años, grupo) están en `const.py`.

Dos decisiones que afectan a todas:
- **Género** = tag del artista que además está en la tabla `genre` de MusicBrainz (2.197
  géneros oficiales). Así "1970s" o "seen live" no cuentan como género. Quedan 978
  géneros distintos en 14.490 artistas.
- **Sello** excluye `[no label]`, que en MusicBrainz significa autoedición, no un sello.

| # | Pregunta | Tipo | Respuesta esperada (medida) |
|---|---|---|---|
| 1 | ¿Qué canciones de artistas de **rock** publicó el sello **Columbia** entre **1970 y 1979**? | Recuperación | **79 canciones** (p. ej. *Heartache People*, Big Brother & The Holding Company, 1970) |
| 2 | ¿Qué canciones en **modo menor** y a más de **140 bpm** interpretan **grupos** (incluidas orquestas y coros)? | Recuperación | **2.849 canciones** |
| 3 | ¿Qué artistas del dataset son o fueron **miembros** de algún grupo del dataset, y de cuál? | Navegación | **2.764 pares** miembro–grupo: 2.031 miembros, 1.855 grupos. Más miembros: Fania All-Stars (13), Miles Davis Quintet (10) |
| 4 | ¿Qué grupos están conectados con **Deep Purple** porque comparten miembros, **directa o indirectamente**? | Navegación (camino `+`) | **219 grupos**; 13 directos (Rainbow, Black Sabbath, Gillan, Kansas…) |
| 5 | ¿Con qué **sellos** ha publicado Deep Purple? (canción → grabación → lanzamiento → sello) | Navegación | **12 sellos** (Harvest, Purple Records, EMI Electrola, Polydor…) |
| 6 | ¿Cuál es el **tempo medio** y la **bailabilidad media** de cada género? (los 10 con más canciones) | Agregación | rock 5.773 canciones, 125,2 bpm, 1,13; hip hop 2.137, **106,7 bpm**, **1,40** (el más bailable y el más lento) |
| 7 | ¿Cuántas canciones hay por **década** y **tipo de artista** (persona, grupo, orquesta, coro…)? | Agregación (jerarquía) | 78.897 canciones con año; década de 2000: 23.185 de grupos y 20.166 de personas |
| 8 | ¿Cuáles son los 10 **sellos** con más canciones y qué **% está en modo mayor**? | Agregación | Columbia 1.537 (67,3 %), EMI 962 (65,6 %), Warner Bros. 917 (70,7 %)… Virgin el más "menor": 55,4 % |

Reparto: 2 de recuperación, 3 de navegación, 3 de agregación. La CQ7 recorre la jerarquía
de clases de artista y la CQ4 un camino de propiedad transitivo.

### Tablas completas de las agregaciones

CQ6 (solo canciones con descriptores acústicos):

| género | canciones | bpm medio | danceability media |
|---|---|---|---|
| rock | 5.773 | 125,22 | 1,13 |
| pop | 3.855 | 121,42 | 1,16 |
| jazz | 3.421 | 122,30 | 1,13 |
| alternative rock | 3.148 | 126,11 | 1,11 |
| electronic | 2.491 | 122,94 | 1,26 |
| pop rock | 2.189 | 125,18 | 1,13 |
| folk | 2.175 | 123,28 | 1,09 |
| hip hop | 2.137 | 106,70 | 1,40 |
| indie rock | 1.880 | 127,80 | 1,09 |
| hard rock | 1.794 | 128,19 | 1,13 |

CQ7 (canciones con año; las 969 canciones de artistas sin tipo no salen en ninguna columna):

| década | Persona | Grupo | Orquesta | Coro | Personaje | Otro |
|---|---|---|---|---|---|---|
| 1920 | 29 | 8 | 0 | 0 | 0 | 0 |
| 1930 | 32 | 8 | 2 | 0 | 0 | 0 |
| 1940 | 45 | 5 | 1 | 0 | 0 | 0 |
| 1950 | 512 | 99 | 6 | 5 | 0 | 0 |
| 1960 | 1.097 | 755 | 3 | 2 | 0 | 0 |
| 1970 | 1.937 | 1.763 | 2 | 5 | 0 | 0 |
| 1980 | 2.781 | 3.424 | 13 | 1 | 2 | 0 |
| 1990 | 8.847 | 9.879 | 55 | 17 | 1 | 1 |
| 2000 | 20.166 | 23.185 | 49 | 23 | 26 | 15 |
| 2010 | 1.487 | 1.147 | 17 | 8 | 0 | 1 |
| 2020 | 142 | 86 | 0 | 0 | 0 | 0 |

Las canciones de 2010 y 2020 son reediciones: el MSD es de 2010 y el año lo rellenó el
lanzamiento de MusicBrainz. Si en SPARQL se pregunta por `:Grupo` con razonamiento, la
columna "Grupo" sumará también orquestas y coros (son subclases).

CQ8:

| sello | canciones | con modo | mayor | % mayor |
|---|---|---|---|---|
| Columbia | 1.537 | 1.227 | 826 | 67,3 |
| EMI | 962 | 555 | 364 | 65,6 |
| Warner Bros. Records | 917 | 727 | 514 | 70,7 |
| Atlantic | 890 | 744 | 504 | 67,7 |
| Epic | 829 | 695 | 453 | 65,2 |
| Capitol Records | 815 | 652 | 470 | 72,1 |
| Virgin | 704 | 563 | 312 | 55,4 |
| RCA | 663 | 460 | 325 | 70,7 |
| Polydor | 580 | 439 | 270 | 61,5 |
| Mercury Records | 446 | 333 | 228 | 68,5 |

## Borradores de SPARQL

Prefijo provisional `:`; los nombres definitivos se fijan en la fase H. `gen:` es el
espacio de IRI de los géneros (`…/genero/<slug>`).

```sparql
# CQ1
SELECT ?c ?titulo ?anio WHERE {
  ?c a :Cancion ; :titulo ?titulo ; :anio ?anio ;
     :interpretadaPor/:tieneGenero gen:rock ;
     :correspondeA/:publicadaEn/:editadoPor/:nombre "Columbia" .
  FILTER (?anio >= "1970"^^xsd:gYear && ?anio <= "1979"^^xsd:gYear)
}

# CQ2
SELECT ?c WHERE {
  ?c :interpretadaPor ?a ; :correspondeA/:descritaPor ?f .
  ?a a/rdfs:subClassOf* :Grupo .
  ?f :modo "minor" ; :bpm ?bpm .
  FILTER (?bpm > 140)
}

# CQ3
SELECT ?miembro ?grupo WHERE { ?miembro :miembroDe ?grupo . }

# CQ4  (grupos que comparten un miembro, recorrido transitivo)
SELECT DISTINCT ?otro WHERE {
  ?dp :nombre "Deep Purple" .
  ?dp (^:miembroDe/:miembroDe)+ ?otro .
  FILTER (?otro != ?dp)
}

# CQ5
SELECT DISTINCT ?sello WHERE {
  ?c :interpretadaPor/:nombre "Deep Purple" ;
     :correspondeA/:publicadaEn/:editadoPor/:nombre ?sello .
}

# CQ6
SELECT ?genero (COUNT(DISTINCT ?c) AS ?n) (AVG(?bpm) AS ?bpmMedio) (AVG(?d) AS ?bailabilidad)
WHERE {
  ?c :interpretadaPor/:tieneGenero ?genero ;
     :correspondeA/:descritaPor ?f .
  ?f :bpm ?bpm ; :danceability ?d .
} GROUP BY ?genero ORDER BY DESC(?n) LIMIT 10

# CQ7
SELECT ?decada ?tipo (COUNT(?c) AS ?n) WHERE {
  ?c :anio ?anio ; :interpretadaPor ?a .
  ?a a ?tipo . ?tipo rdfs:subClassOf* :Artista .
  BIND (FLOOR(YEAR(?anio) / 10) * 10 AS ?decada)
} GROUP BY ?decada ?tipo ORDER BY ?decada

# CQ8
SELECT ?sello (COUNT(DISTINCT ?c) AS ?n)
       (100 * SUM(IF(?modo = "major", 1, 0)) / COUNT(?modo) AS ?pctMayor)
WHERE {
  ?c :correspondeA/:publicadaEn/:editadoPor/:nombre ?sello .
  OPTIONAL { ?c :correspondeA/:descritaPor/:modo ?modo }
} GROUP BY ?sello ORDER BY DESC(?n) LIMIT 10
```

Diferencias previsibles al correrlas en Fuseki (fase K), para no sorprenderse:
- En la Etapa 1 cada canción eligió **un** lanzamiento. Si dos canciones del MSD caen en
  la misma grabación con lanzamientos distintos, la grabación tendrá dos y las CQ 1, 5 y
  8 pueden contar alguna canción de más.
- `YEAR()` sobre `xsd:gYear` depende del motor; si falla, la década se saca con
  `SUBSTR(STR(?anio), 1, 3)`.

## Revisión del modelo de la Etapa 1

Se pasó cada pregunta por `docs/modelo_conceptual.ttl` marcando qué clases y propiedades
usaría su consulta.

### 1. Lo que ya tiene y las preguntas usan

- Clases `Cancion`, `Artista`, `Grabacion`, `Lanzamiento`, `Sello`, `FeaturesAcusticas`.
- Relaciones `interpretadaPor`, `correspondeA`, `publicadaEn`, `editadoPor`, `descritaPor`:
  la cadena canción → grabación → lanzamiento → sello sostiene las CQ 1, 5 y 8.
- Datos `titulo`, `anio`, `bpm`, `danceability`, `modo`, `nombreSello`.

### 2. Lo que falta

| Falta | Para qué CQ | De dónde sale |
|---|---|---|
| Clase `Genero` y relación `tieneGenero` (Artista → Genero) | 1, 6 | tags de `artists.csv` filtrados por la tabla `genre` de MB |
| Subclases `Persona` y `Grupo` de `Artista`, y `Orquesta`, `Coro` de `Grupo` | 2, 7 | columna `tipo` de `artists.csv` (13.562 Group, 12.244 Person, 64 Orchestra, 20 Choir) |
| Relación `miembroDe` (Persona → Grupo) | 3, 4 | `l_artist_artist` con tipo `member of band`: **hay que exportar un CSV nuevo** (`artist_relations.csv`, con columna `fuente`) en la fase I |
| Un `nombre` común para artista y sello | 4, 5 | ya está en los CSV; hoy el modelo solo tiene `nombreSello` |
| `duracionMs` de la grabación, separada de `duracion` (segundos) de la canción | ninguna, pero evita mezclar unidades | `recording.length` |
| `mbidAntiguo` del artista | ninguna, pero hace falta para los artistas fusionados (IRI con `mbid_canonico`) | `artists.csv.artist_mbid` |

Lo que **no** está en los datos y por eso no hay CQ sobre ello:
- **Jerarquía de géneros** (`l_genre_genre`): no se extrajo del dump en la Etapa 1. La
  jerarquía navegable del modelo es la de tipos de artista y el camino `miembroDe`.
- **Colaboraciones**: en el dump hay `collaboration`, pero solo 83 pares con los dos
  artistas en nuestro dataset, frente a 2.764 pares únicos de `member of band`. No da para una CQ.

### 3. Lo que tiene y ninguna pregunta usa

| Sobra | Decisión |
|---|---|
| `tagsArtista`, `tagsGrabacion` (texto con `;`) | se retiran: los reemplaza `tieneGenero` con IRI |
| `tipoArtista` (texto) | se retira: lo reemplazan las subclases |
| `anioMsd` | se retira: `anio` + `fuenteAnio` ya dicen el año y de dónde salió; el 0 del MSD era un nulo |
| `metodoMatch` en `Grabacion` | se mueve a `Cancion`: describe el emparejamiento de *esa* fila del MSD, no la grabación |
| `genero` (género del artista, M/F) | se mantiene como dato del artista; no estorba y es información real |
| `releaseMsd`, `trackId`, `recordingMbid`, `artistMbid`, `releaseMbid` | se mantienen: son los identificadores de correspondencia que pide el enunciado |
| `area`, `anioInicio`, `anioFin`, `wikidata`, `pais`, `tipoLanzamiento` | se mantienen: ficha del explorador, sin costo |
| Histograma de bpm, `mfccZeroMean`, afinación, `onsetRate`, `dynamicComplexity` | se mantienen como datos de `FeaturesAcusticas`; ninguna CQ los usa pero son la parte del dataset que viene de AcousticBrainz |
