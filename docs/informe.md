# Etapa 1 — Extracción y enriquecimiento de información musical

Ignacio Chaparro · Web Semántica (MISIS) · Grupo 5

## 1. Fuentes utilizadas

El punto de partida es `grupo_5.csv`: 100.000 canciones del Million Song Dataset con
`track_id`, `title`, `artist_name`, `release`, `year`, `duration` y `artist_mbid`. Ese
último campo, presente y válido en el 100 % de las filas, es la bisagra con el resto: es un
identificador de MusicBrainz, así que la canción ya viene anclada a un artista concreto del
grafo y el trabajo se reduce a encontrar la **grabación**.

Todas las fuentes externas se consumen como volcados completos, no vía API: la API web de
MusicBrainz permite una petición por segundo, y solo resolver las grabaciones de las
100.000 canciones habría llevado unas 28 horas.

| Fuente | Versión | Qué aporta |
|---|---|---|
| MusicBrainz, dump core (`mbdump`, 7,0 GB) | `20260909-002431` | Grabaciones, lanzamientos, grupos de lanzamiento, artistas, sellos, países y las relaciones entre ellos, incluidas las URL externas (Wikidata, Discogs, etc.) |
| MusicBrainz, dump derived (492 MB) | `20260909-002431` | Etiquetas por entidad (`artist_tag`, `recording_tag`, `release_group_tag`), de donde salen los géneros |
| AcousticBrainz, *lowlevel features* (2,8 GB) | `20220623` | Descriptores de audio: tempo, tonalidad, escala, sonoridad y características rítmicas |
| AcousticBrainz labs, mapeo `msd-mbid-2016-01` (13 MB) | 2016-01 | 377.406 correspondencias MSD→MBID, usadas para **validar** la reconciliación propia |

De MusicBrainz se extraen 34 tablas de las 236 del volcado: las entidades que el modelo
conceptual necesita más las tablas de enlace y los vocabularios controlados sin los que
los identificadores numéricos del volcado no significan nada.

Dos limitaciones conocidas desde el principio: AcousticBrainz dejó de recibir datos en
2022, así que su cobertura será parcial, y el mapeo MSD→MBID cubre 377.406 de los
1.000.000 de ids del MSD, insuficiente como ruta principal de reconciliación.

## 2. Proceso de extracción

Cuatro scripts, ejecutados dentro de un contenedor Docker.

**Descarga (`00_download.py`).** El directorio del volcado de MusicBrainz cambia cada
semana, así que el script resuelve `fullexport/LATEST` en tiempo de ejecución y deja la
versión resuelta en `MB_VERSION.txt` como registro de procedencia. Cada archivo se
contrasta contra el checksum publicado; si no cuadra, se borra y el proceso se detiene.
Se descarga a disco (11 GB, ~40 minutos) en vez de descomprimir en *streaming*: cuesta
almacenamiento temporal, pero permite verificar checksums y reanudar tras un corte.

**Extracción (`01_extract.py`).** Un `.tar.bz2` no admite acceso aleatorio: aunque solo
interesen 34 tablas de 236, hay que recorrer el flujo entero. Se usa `lbzip2` (descompresión
paralela) y `tar` con los miembros deseados como patrones: una sola pasada y solo se
escriben las tablas seleccionadas. Los 45 GB del volcado nunca se materializan; quedan
21 GB de TSV en 387 segundos. Las tablas mayores: `track` (57,8 M filas), `recording`
(40,1 M), `url` (21,6 M).

**Cabeceras (`02_headers.py`).** Los TSV vienen sin nombres de columna —formato `COPY` de
PostgreSQL—; el orden sale del DDL oficial (`CreateTables.sql`). El parser cuenta
paréntesis para distinguir columnas de las restricciones `CHECK (...)` multilínea y aborta
si `artist` no da 19 columnas o `recording` 9.

**Carga (`03_load_duckdb.py`).** Las 34 tablas más el mapeo MSD se materializan en una
base DuckDB de 9,5 GB en ~16 minutos, con la memoria acotada a 2 GB y derrame a disco
(sin ese límite, las tablas de 40–58 M de filas saturaban la RAM). Los conteos de cada
tabla se contrastan contra los medidos en la extracción.

## 3. Reconciliación

La reconciliación de artistas se reduce a una verificación: 26.242 de los 27.352 MBID del
MSD existen tal cual en el dump y 642 más se resuelven vía `artist_gid_redirect` (artistas
fusionados desde 2010); solo 468 quedan sin resolver. El problema real es asignar a cada
canción su **grabación**, que el MSD no trae.

En lugar de comparar cada título contra los 40 millones de grabaciones, se acotan los
candidatos a las grabaciones del propio artista (8,6 millones en total, unos cientos por
canción) y se decide en cascada, cada método solo sobre lo que el anterior no resolvió:

1. **Título exacto** (normalizado: minúsculas, sin acentos, solo alfanumérico): 66.446.
2. **Sin sufijo**: igual, quitando el sufijo entre paréntesis típico del MSD
   ("(Album Version)"): 8.970.
3. **Difuso** (`token_set_ratio` ≥ 90 con duración a ±15 s): 5.303.

Cobertura total: **80.719 de 100.000 (80,7 %)**, en 40 segundos. Los empates se resuelven
prefiriendo duración dentro de ±15 s, luego la grabación más referenciada por la tabla
`track` y luego la menor diferencia de duración.

Como medida de precisión independiente se contrastó contra el mapeo `msd-mbid-2016-01`,
que cubre 39.513 de nuestras filas: el acuerdo exacto es del 57,5 %, pero la gran mayoría
de los desacuerdos son grabaciones **duplicadas sin fusionar** en MusicBrainz (mismo
título normalizado y mismo crédito de artista, distinto MBID): contándolas como acuerdo,
la coincidencia sube al **82,9 %**. El desacuerdo restante no es atribuible solo a nuestro
proceso: el mapeo de AB también se generó por matching automático en 2016.

## 4. Integración y limpieza

Con el matching resuelto, el enriquecimiento son joins sobre la base DuckDB
(`05_enrich.py` y `06_acousticbrainz.py`), que producen seis CSV en `data/processed/`,
todos con una columna `fuente` que registra la procedencia del dato (`musicbrainz`,
`musicbrainz-derived` o `acousticbrainz`):

| Archivo | Filas | Contenido |
|---|---|---|
| `artists.csv` | 26.884 | tipo, género, país, años de actividad, top 5 de tags y URL de Wikidata por artista |
| `releases.csv` | 80.706 | edición más antigua de cada grabación: año, mes, país, grupo de ediciones y tipo |
| `labels.csv` | 56.509 | sello y número de catálogo de esas ediciones |
| `tags.csv` | 285.855 | tags de la comunidad por grabación y por grupo de ediciones |
| `urls.csv` | 499.891 | enlaces externos (Wikidata, Discogs, etc.) de artistas y ediciones |
| `features.csv` | 45.211 | features acústicas de AcousticBrainz (bpm, tonalidad, danceability…) |

Decisiones de limpieza principales:

- **Una edición por grabación.** Una grabación aparece en decenas de discos. Se elige la
  de fecha más antigua, prefiriendo ediciones oficiales sobre bootlegs y promos pero sin
  descartar estas últimas cuando son lo único que hay. Solo 13 grabaciones quedan sin
  edición.
- **Wikidata sin salir del dump:** el enlace por artista sale de `l_artist_url → url`
  filtrando por `link_type = 'wikidata'`, sin consultar ningún servicio externo.
- **Features acústicas:** los volcados de AcousticBrainz (~29,5 M de filas por categoría)
  traen varias *submissions* por grabación; se conserva una por MBID (la de menor
  `submission_offset`, determinista). Sus MBID son de 2022, así que se canonicalizan
  contra `recording_gid_redirect` antes del cruce.
- **Cobertura de AcousticBrainz: 45.211 de 80.719 matches (56 %).** Limitación de la
  fuente (congelada en 2022), no del proceso; se documenta y las filas sin features
  quedan con esos campos vacíos.

## 5. Consolidación y entrega

El paso final (`07_export.py`) une todo en `songs_final.csv`: **las 100.000 filas originales**
(joins externos: ninguna canción se pierde por falta de cobertura) con 38 columnas: las 7
del MSD intactas, el MBID de grabación con su método de match, la edición (título, país,
tipo), los sellos, el perfil del artista (tipo, género, país, actividad, tags, Wikidata),
los tags de la grabación y las 14 features acústicas. Lo multivalor se aplana con `;`
para mantener una fila por canción; el detalle completo queda en los CSV por entidad.

La consolidación resuelve además el `year`: el MSD lo trae a 0 en 45.219 filas, y el año
de la edición más antigua rellena 24.116 de ellas. `songs_final.csv` lleva una columna `anio`
consolidada (cobertura final: 78.897 filas, 78,9 %) y una `fuente_anio` que dice si el
año viene del MSD o de MusicBrainz — la misma idea de procedencia que la columna `fuente`
del resto de CSVs.

El entregable de datos son los ocho CSV de `data/processed/` (`songs_final.csv` más los siete
anteriores, incluido `matches.csv` con el método y score de cada correspondencia), y el
modelo conceptual está en `docs/modelo_conceptual.ttl`, planteado directamente en RDFS
(sintaxis Turtle): seis clases —canción, artista, grabación, lanzamiento, sello y
features acústicas—, las relaciones entre ellas como propiedades de objeto con dominio
y rango, y cada columna de `songs_final.csv` como propiedad de datos con su tipo `xsd`.
El análisis de completitud del CSV final (porcentaje de dato por columna, cobertura por
fuente, años recuperados) está en `notebooks/analisis_completitud.ipynb`.

## 6. Tecnologías utilizadas

Todo corre dentro de un único contenedor Docker (`python:3.12-slim`): reproducir el ETL no
exige instalar nada en la máquina anfitriona.

- **DuckDB** como motor de consulta: ingiere los TSV del dump con `read_csv` y los
  materializa en una base de un solo archivo. Se descartó PostgreSQL porque exigía
  importar los ~45 GB del volcado completo sin aportar nada a un caso de uso que es un
  puñado de joins analíticos.
- **pandas** para la exploración inicial; **rapidfuzz** para la similitud de títulos;
  **unidecode** para normalizar acentos antes de comparar.
- **lbzip2** y **zstd** para descomprimir los dumps; lbzip2 paraleliza los 7 GB del core
  frente a la hora aproximada de `bzip2` monohilo.
- **make** como única interfaz: cada paso es `make 00`, `make 01`, …, y la secuencia
  completa `make all`. Sin orquestador ni framework: scripts planos y `make` solo
  encapsula la invocación de Docker.

## 7. Retos y problemas encontrados

- **Dumps que fallan a mitad de descarga.** El espejo de MetaBrainz se colgó y la
  reanudación con `curl -C -` produjo un archivo corrupto. La verificación de checksums
  tras cada descarga lo detectó a tiempo; sin ella, el error habría aparecido mucho
  después, en plena extracción.
- **TSV sin cabecera y un DDL con trampas.** El orden de columnas sale del DDL oficial,
  pero sus bloques `CHECK (...)` multilínea contienen nombres que parecen columnas: un
  parser línea a línea "duplicaba" columnas en `artist` y `link`. Se resolvió contando
  paréntesis y verificando contra el número de columnas conocido (19 en `artist`).
- **Los géneros no estaban donde se esperaba.** Los tags por entidad no vienen en el dump
  core sino en el derivado, que hubo que sumar a la descarga a mitad de proyecto.
- **La carga saturaba la RAM.** DuckDB intenta retener las tablas en memoria antes de
  escribirlas; con tablas de 40–58 M de filas se comía toda la máquina. Se acotó con
  `memory_limit=2GB` y directorio temporal en disco.
- **Un CSV sin cabecera leído como si la tuviera.** El lector convirtió la primera fila
  de datos del mapeo MSD→MBID en nombres de columna; pasó inadvertido una fase entera
  hasta que el contraste de validación lo destapó. Moraleja: los conteos de control se
  comprueban en cuanto se carga la fuente, no al usarla.
- **Un 41 % de acuerdo que no era un fallo.** El primer contraste contra AcousticBrainz
  parecía condenar el matching, pero la causa era otra: MusicBrainz está lleno de
  grabaciones duplicadas sin fusionar y cada proceso elegía un duplicado distinto.
  Desempatar por la grabación más referenciada y medir el acuerdo a nivel de
  título+artista dio la imagen real (82,9 %).
