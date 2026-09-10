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

De MusicBrainz se extraen 33 tablas de las 236 del volcado. La selección no es arbitraria:
cubre las entidades que el modelo conceptual necesita (grabación, lanzamiento, artista,
sello, obra, género) más las tablas de enlace y los vocabularios controlados (`artist_type`,
`gender`, `language`, `script`, `link_type`) sin los que los identificadores numéricos del
volcado no significan nada.

Dos limitaciones conocidas desde el principio: AcousticBrainz dejó de recibir datos en 2022,
así que su cobertura sobre nuestro conjunto será parcial, y el mapeo MSD→MBID cubre 377.406
de los 1.000.000 de identificadores del MSD, insuficiente como ruta principal de
reconciliación.

## 2. Proceso de extracción

_La parte de carga en DuckDB se completa en la fase C._

La extracción está resuelta con dos scripts que se ejecutan dentro del contenedor.

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
solo interesen 33 tablas de 236, hay que descomprimir el flujo entero. Se usa `lbzip2`, que
paraleliza la descompresión, y se le pasan a `tar` los miembros deseados como patrones, de
forma que el flujo se recorre una sola vez y solo se escriben en disco las tablas
seleccionadas. Los 45 GB del volcado completo nunca se materializan: quedan 21 GB de TSV.
El core tarda 374 segundos y el derivado 13.

El resultado son 33 archivos TSV sin cabecera —el volcado usa el formato `COPY` de
PostgreSQL— más el mapeo MSD→MBID descomprimido. Las tablas mayores son `track`
(57,8 millones de filas), `recording` (40,1 millones) y `url` (21,6 millones).

## 3. Reconciliación

_Fase D. Debe incluir la tasa de match por método y el contraste contra el mapeo
`msd-mbid-2016-01` de AcousticBrainz._

## 4. Integración y limpieza

_Fase E._

## 5. Tecnologías utilizadas

Todo el proceso corre dentro de un único contenedor Docker (`python:3.12-slim`), de modo
que la reproducción no exige instalar nada en la máquina anfitriona y el trabajo
intermedio se elimina por completo con `docker compose down -v`.

- **DuckDB** como motor de consulta, leyendo los TSV del dump de MusicBrainz directamente
  con `read_csv`. Se descartó PostgreSQL porque exigía importar ~45 GB (varias horas) sin
  aportar nada al caso de uso, que es un puñado de joins analíticos de una sola pasada.
- **pandas** para la manipulación del dataset de entrada y la escritura de los CSV finales.
- **rapidfuzz** para la similitud de títulos en el paso de reconciliación.
- **unidecode** para la normalización de acentos previa a la comparación de cadenas.
- **lbzip2** y **zstd** para descomprimir los dumps; lbzip2 descomprime en paralelo los
  7 GB del dump core, frente a la hora aproximada que tarda `bzip2` monohilo.

Se descartó el uso de la API web de MusicBrainz: su límite de una petición por segundo
implicaba unas 28 horas solo para resolver las grabaciones de las 100.000 canciones.

## 6. Retos y problemas encontrados

_Continuo, destilado de `bitacora.md`._
