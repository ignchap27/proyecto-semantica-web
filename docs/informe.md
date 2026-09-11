# Etapa 1 — Extracción y enriquecimiento de información musical

Ignacio Chaparro · Web Semántica (MISIS) · Grupo 5

> Documento en construcción. Cada sección se redacta en la fase que le corresponde; en la
> fase F se recorta a 4 páginas y se pule. La materia prima está en `bitacora.md`.

## 1. Fuentes utilizadas

El punto de partida es `grupo_5.csv`: 100.000 canciones del Million Song Dataset con
`track_id`, `title`, `artist_name`, `release`, `year`, `duration` y `artist_mbid`. Ese
último campo, presente y válido en el 100 % de las filas, es la bisagra con el resto: es un
identificador de MusicBrainz, así que la canción ya viene anclada a un artista concreto del
grafo y el trabajo se reduce a encontrar la **grabación**.

Todas las fuentes externas se consumen como volcados completos, no vía API. Se descartó la
API web de MusicBrainz por su límite de una petición por segundo: solo resolver las
grabaciones de las 100.000 canciones habría llevado unas 28 horas.

| Fuente | Versión | Qué aporta |
|---|---|---|
| MusicBrainz, dump core (`mbdump`, 7,0 GB) | `20260909-002431` | Grabaciones, lanzamientos, grupos de lanzamiento, artistas, sellos, obras, países, idiomas, y las relaciones entre ellos, incluidas las URL externas (Wikidata, Discogs, etc.) |
| MusicBrainz, dump derived (`mbdump-derived`, 492 MB) | `20260909-002431` | Etiquetas por entidad (`artist_tag`, `recording_tag`, `release_group_tag`), de donde salen los géneros |
| AcousticBrainz, *lowlevel features* (2,8 GB) | `20220623` | Descriptores de audio: tempo, tonalidad, escala, sonoridad y características rítmicas |
| AcousticBrainz labs, mapeo `msd-mbid-2016-01` (13 MB) | 2016-01 | 377.406 correspondencias MSD→MBID, usadas para **validar** la reconciliación propia |

De MusicBrainz se extraen 34 tablas de las 236 del volcado. La selección no es arbitraria:
cubre las entidades que el modelo conceptual necesita (grabación, lanzamiento, artista,
sello, obra, género) más las tablas de enlace y los vocabularios controlados (`artist_type`,
`gender`, `language`, `script`, `link_type`) sin los que los identificadores numéricos del
volcado no significan nada.

Dos limitaciones conocidas desde el principio: AcousticBrainz dejó de recibir datos en 2022,
así que su cobertura sobre nuestro conjunto será parcial, y el mapeo MSD→MBID cubre 377.406
de los 1.000.000 de identificadores del MSD, insuficiente como ruta principal de
reconciliación.

## 2. Proceso de extracción

La extracción está resuelta con cuatro scripts que se ejecutan dentro del contenedor.

**Descarga (`00_download.py`).** El directorio del volcado de MusicBrainz cambia cada
semana, así que el script resuelve `fullexport/LATEST` en tiempo de ejecución en vez de
llevar la fecha fija, y deja la versión resuelta en `MB_VERSION.txt` como registro de
procedencia. Cada archivo se contrasta contra el checksum publicado por el servidor
(`MD5SUMS` en MusicBrainz, `sha256sums` en AcousticBrainz); si no cuadra, se borra y el
proceso se detiene, de modo que un volcado truncado no llega nunca a las fases siguientes.
Los archivos ya verificados no se vuelven a descargar. Total: 11 GB en unos 40 minutos.

Se optó por descargar a disco en lugar de encadenar descarga y descompresión en *streaming*.
Cuesta 11 GB de almacenamiento temporal, pero permite verificar los checksums, reanudar tras
un corte y volver a extraer una tabla olvidada sin repetir la descarga. La decisión se
justificó sola: el servidor espejo se quedó colgado a mitad de una descarga y la reanudación
produjo un archivo corrupto que solo se detectó gracias a la verificación.

**Extracción (`01_extract.py`).** Un volcado `.tar.bz2` no admite acceso aleatorio: aunque
solo interesen 34 tablas de 236, hay que descomprimir el flujo entero. Se usa `lbzip2`, que
paraleliza la descompresión, y se le pasan a `tar` los miembros deseados como patrones, de
forma que el flujo se recorre una sola vez y solo se escriben en disco las tablas
seleccionadas. Los 45 GB del volcado completo nunca se materializan: quedan 21 GB de TSV.
El core tarda 374 segundos y el derivado 13.

El resultado son 34 archivos TSV sin cabecera —el volcado usa el formato `COPY` de
PostgreSQL— más el mapeo MSD→MBID descomprimido. Las tablas mayores son `track`
(57,8 millones de filas), `recording` (40,1 millones) y `url` (21,6 millones).

**Cabeceras (`02_headers.py`).** Los TSV no traen nombres de columna: el orden sale del
DDL oficial (`CreateTables.sql`). El parser cuenta paréntesis para distinguir columnas de
las restricciones `CHECK (...)` multilínea, que contienen nombres que parecen
declaraciones, y aborta si `artist` no da 19 columnas o `recording` 9 —la señal de que el
esquema publicado se desalineó con el volcado.

**Carga (`03_load_duckdb.py`).** Las 34 tablas más el mapeo MSD se materializan en una
base DuckDB de 9,5 GB (los 21 GB de TSV comprimen a menos de la mitad). La carga completa
tarda unos 16 minutos con un consumo de memoria acotado a 2 GB: DuckDB por defecto intenta
retener las tablas en RAM antes de escribirlas, lo que con tablas de 40–58 millones de
filas saturaba la máquina; limitando la memoria y dando un directorio temporal en disco,
el excedente derrama y el proceso se mantiene en ~1 GB. Los conteos de filas de cada tabla
cargada se contrastan contra los medidos en la extracción.

## 3. Reconciliación

El dataset de entrada trae el MBID del artista en el 100 % de las filas, así que la
reconciliación de artistas se reduce a una verificación: 26.242 de los 27.352 MBID
existen tal cual en el dump y 642 más se resuelven vía `artist_gid_redirect` (artistas
fusionados desde 2010, cuando se generó el MSD); solo 468 quedan sin resolver. El
problema real es asignar a cada canción su **grabación** (recording), que el MSD no trae.

En lugar de comparar cada título contra los 40 millones de grabaciones, se acotan los
candidatos a las grabaciones del propio artista (8,6 millones en total, unos cientos por
canción) y se decide en cascada, cada método solo sobre lo que el anterior no resolvió:

1. **Título exacto** (normalizado: minúsculas, sin acentos, solo alfanumérico): 66.446.
2. **Sin sufijo**: igual, quitando el sufijo entre paréntesis típico del MSD
   ("(Album Version)"): 8.970.
3. **Difuso** (`token_set_ratio` ≥ 90 con duración a ±15 s): 5.303.

Cobertura total: **80.719 de 100.000 (80,7 %)**, en 40 segundos. Los empates se
resuelven prefiriendo duración dentro de ±15 s, luego la grabación más referenciada por
la tabla `track` y luego la menor diferencia de duración.

Como medida de precisión independiente se contrastó contra el mapeo `msd-mbid-2016-01`
de AcousticBrainz, que cubre 39.513 de nuestras filas: el acuerdo exacto es del 57,5 %,
pero un análisis de los desacuerdos mostró que la gran mayoría son grabaciones
**duplicadas sin fusionar** en MusicBrainz (mismo título normalizado y mismo crédito de
artista, distinto MBID): contándolas como acuerdo, la coincidencia sube al **82,9 %**. El
desacuerdo restante no es atribuible solo a nuestro proceso: el mapeo de AB también se
generó por matching automático en 2016.

## 4. Integración y limpieza

Con el matching resuelto, el enriquecimiento son joins sobre la base DuckDB. El paso
`05_enrich.py` produce cinco CSV consolidados en `data/processed/`, todos con una columna
`fuente` que registra la procedencia del dato (`musicbrainz`, `musicbrainz-derived` o
`acousticbrainz`):

| Archivo | Filas | Contenido |
|---|---|---|
| `artists.csv` | 26.884 | tipo, género, país, años de actividad, top 5 de tags y URL de Wikidata por artista |
| `releases.csv` | 80.706 | edición más antigua de cada grabación: año, mes, país, grupo de ediciones y tipo |
| `labels.csv` | 56.509 | sello y número de catálogo de esas ediciones |
| `tags.csv` | 285.855 | tags de la comunidad por grabación y por grupo de ediciones |
| `urls.csv` | 499.891 | enlaces externos (Wikidata, Discogs, etc.) de artistas y ediciones |
| `features.csv` | 45.211 | features acústicas de AcousticBrainz (bpm, tonalidad, danceability…) |

Las decisiones de limpieza principales:

- **Una edición por grabación.** Una grabación aparece en decenas de discos
  (reediciones, recopilatorios, por país). Se elige la de fecha más antigua según
  `release_country`, prefiriendo ediciones oficiales sobre bootlegs y promos, pero sin
  descartar estas últimas cuando son lo único que hay. Solo 13 grabaciones quedan sin
  edición. El año resultante servirá en la fase F para rellenar las 45.219 filas cuyo
  `year` del MSD es 0.
- **Wikidata sin salir del dump:** el enlace por artista sale de `l_artist_url → url`
  filtrando por `link_type = 'wikidata'`, sin consultar ningún servicio externo.
- **Features acústicas (`06_acousticbrainz.py`).** Los tres volcados CSV de
  AcousticBrainz (~29,5 M de filas cada uno) traen varias *submissions* por grabación;
  se conserva una por MBID (la de menor `submission_offset`, determinista). Como sus
  MBID son de 2022, se canonicalizan contra `recording_gid_redirect` antes del cruce:
  el conjunto objetivo pasa de 80.719 a 232.261 MBIDs contando los redirigidos.
- **Cobertura de AcousticBrainz: 45.211 de 80.719 matches (56 %).** AcousticBrainz se
  congeló en 2022, así que esta es una limitación de la fuente, no del proceso; se
  documenta y las filas sin features quedan con esos campos vacíos en la exportación
  final, que conserva las 100.000 canciones.

## 5. Tecnologías utilizadas

Todo el proceso corre dentro de un único contenedor Docker (`python:3.12-slim`), de modo
que la reproducción no exige instalar nada en la máquina anfitriona y el trabajo
intermedio se elimina por completo con `docker compose down -v`.

- **DuckDB** como motor de consulta: ingiere los TSV del dump con `read_csv` y los
  materializa en una base de un solo archivo. Se descartó PostgreSQL porque exigía
  importar los ~45 GB del volcado completo (varias horas) sin aportar nada al caso de
  uso, que es un puñado de joins analíticos.
- **pandas** para la manipulación del dataset de entrada y la escritura de los CSV finales.
- **rapidfuzz** para la similitud de títulos en el paso de reconciliación.
- **unidecode** para la normalización de acentos previa a la comparación de cadenas.
- **lbzip2** y **zstd** para descomprimir los dumps; lbzip2 descomprime en paralelo los
  7 GB del dump core, frente a la hora aproximada que tarda `bzip2` monohilo.
- **make** como única interfaz del ETL: cada paso se lanza con `make 00`, `make 01`, … y
  la secuencia completa con `make all`. No hay orquestador ni framework de pipelines; los
  pasos son scripts independientes y `make` solo encapsula la invocación de Docker.

Se descartó el uso de la API web de MusicBrainz: su límite de una petición por segundo
implicaba unas 28 horas solo para resolver las grabaciones de las 100.000 canciones.

## 6. Retos y problemas encontrados

_Se destila de `bitacora.md`; se redacta en detalle en la fase F. Apuntados hasta ahora:_

- El servidor espejo de MetaBrainz se cuelga a mitad de descarga y una reanudación con
  `curl -C -` produjo un archivo corrupto; la verificación de checksums tras cada descarga
  fue lo que lo detectó a tiempo.
- Los TSV del volcado no traen cabecera y el DDL tiene trampas de parseo (los `CHECK`
  multilínea); se resolvió contando paréntesis y verificando contra el número de columnas
  conocido.
- Los tags/géneros no están en el volcado core sino en el derivado, que hubo que sumar.
- La carga inicial en DuckDB agotaba la RAM de la máquina; se acotó con `memory_limit` y
  derrame a disco.
- El mapeo MSD→MBID venía sin cabecera y el lector de CSV convirtió la primera fila de
  datos en nombres de columna; pasó inadvertido una fase entera hasta que el contraste lo
  destapó.
- El primer contraste contra AcousticBrainz dio un acuerdo del 41 % que parecía un fallo
  del matching y resultó ser otra cosa: MusicBrainz está lleno de grabaciones duplicadas
  sin fusionar y cada proceso elegía un duplicado distinto. Desempatar por la grabación
  más referenciada y medir el acuerdo a nivel de título+artista dio la imagen real
  (82,9 %).
