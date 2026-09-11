# Proyecto de Semántica Web — Etapa 1

Ignacio Chaparro

Enriquecimiento de un dataset de **100.000 canciones** del Million Song Dataset
(`data/grupo_5.csv`) con información extraída de fuentes externas, estableciendo
correspondencias reales entre cada canción y las entidades de esas fuentes.

Entregables de la etapa: CSVs consolidados con procedencia por registro, modelo conceptual
preliminar, informe de máximo 4 páginas y este código reproducible.

## Dataset de entrada

`data/grupo_5.csv` — 100.000 filas, 7 columnas:

| Columna | Notas |
|---|---|
| `track_id` | id del MSD, único en las 100.000 filas |
| `title` | |
| `artist_name` | 31.788 valores distintos |
| `release` | nombre del álbum, 61.385 valores distintos |
| `year` | **45.219 filas valen `0`** (sentinela del MSD) |
| `duration` | segundos |
| `artist_mbid` | MBID de artista, presente y válido en el **100 %** de las filas |

## Fuentes

| Fuente | Qué aporta | Tamaño |
|---|---|---|
| [MusicBrainz](https://musicbrainz.org/doc/MusicBrainz_Database/Schema) core (`mbdump`) | recordings, releases, release groups, artistas, sellos, obras, relaciones y URLs externas | 7 GB |
| MusicBrainz derived (`mbdump-derived`) | tags y géneros por entidad | 492 MB |
| [AcousticBrainz](https://acousticbrainz.org/data) lowlevel features | tempo, tonalidad, escala, sonoridad, features rítmicas | ~2,8 GB |
| AcousticBrainz labs, mapeo `msd-mbid-2016-01` | validación del matching MSD→MBID | 13 MB |

## Estructura del repo

```
.
├── Makefile                # atajos: `make 00`, `make all`, `make shell`...
├── Dockerfile              # python:3.12-slim + curl, lbzip2, zstd
├── docker-compose.yml      # un solo servicio (etl) + volumen `work` para los crudos
├── requirements.txt        # duckdb, pandas, rapidfuzz, unidecode
├── const.py                # rutas, URLs y listas de tablas
├── data/
│   ├── grupo_5.csv         # entrada (solo lectura)
│   └── processed/          # CSVs finales (entregables)
├── docs/
│   ├── Proyecto_Etapa1_MISIS.pdf
│   ├── bitacora.md         # registro de problemas y decisiones
│   ├── informe.md          # entregable de 4 páginas, se redacta en paralelo
│   └── modelo_conceptual.md
└── scripts/                # un script por paso, se corren en orden
    ├── 00_download.py      # baja los dumps a /data/raw y verifica checksums
    ├── 01_extract.py       # saca las 33 tablas que usamos a /data/interim
    ├── 02_headers.py       # parsea CreateTables.sql -> headers.json (los TSV no traen cabecera)
    └── 03_load_duckdb.py   # carga los TSV como tablas en /data/mb.duckdb
```

## Requisitos

Solo **Docker** y `make`. Nada se instala en la máquina anfitriona.

Espacio en disco: 11 GB de descargas + 21 GB de TSV extraídos + 9,5 GB de base DuckDB
(medido en las fases B y C).

## Cómo replicar el ETL

Todo se lanza con `make`. No hace falta escribir un solo comando de Docker.

| Comando | Qué hace |
|---|---|
| `make build` | construye la imagen (opcional: los pasos la construyen solos la primera vez) |
| `make check` | verifica el entorno: dependencias, binarios y dataset de entrada |
| `make 00` | corre el paso 00 y sigue su salida en vivo |
| `make all` | corre todos los pasos existentes, en orden |
| `make logs-00` | relee los logs de un paso que ya terminó |
| `make shell` | abre un `bash` dentro del contenedor (para mirar `/data`) |
| `make clean` | borra los contenedores `etl_*` parados |
| `make nuke` | **destruye** el volumen con los ~32 GB de datos (pide confirmación) |

Los pasos salen de los nombres de `scripts/`, así que al añadir `scripts/02_headers.py`
aparece `make 02` sin tocar el Makefile.

Cada paso corre en un contenedor con nombre (`etl_00`, `etl_01`, …), en segundo plano y
**sin `--rm`**: `make` te muestra la salida en vivo, pero **Ctrl-C solo corta el
seguimiento de los logs, no el proceso**. Vuelve a engancharte con `make logs-00`. Al
terminar imprime el código de salida y el contenedor queda en `Exited` con sus logs
intactos.

Relanzar un paso borra automáticamente su contenedor anterior. Si el paso **todavía está
corriendo**, el borrado falla a propósito y verás `container name is already in use`: nada
se ha matado, sigue en marcha.

**Borrar contenedores no borra datos.** Los TSV y la base DuckDB viven en el volumen
`work`, independiente de los contenedores. Lo único que destruye datos es `make nuke` (ver
[Cómo borrar todo](#cómo-borrar-todo)).

Mientras haya contenedores viejos sin borrar, `docker compose` avisa de *orphan
containers*. Es ruido, no un error: los nombra así porque no son parte de ningún servicio
levantado. Se calla con `make clean`.

### Fase A — Andamiaje

```bash
make check
```

Construye la imagen si hace falta (~1 min desde cero) y comprueba de una vez las tres
cosas. Tiene que imprimir:

- DuckDB 1.5.5, pandas 2.3.3, RapidFuzz 3.14.6 y Unidecode 1.4.0;
- las rutas de `curl`, `lbzip2` y `zstd` (no vienen de pip, van en el `Dockerfile`);
- `100001 data/grupo_5.csv`, o sea las 100.000 canciones más la cabecera.

### Fase B — Descarga y extracción

```bash
make 00
make 01
```

**`00_download.py`** (`make 00`) resuelve `fullexport/LATEST` (versión usada: `20260909-002431`), deja
la versión en `/data/raw/MB_VERSION.txt` y baja a `/data/raw`:

| Archivo | Tamaño | Checksum |
|---|---|---|
| `mbdump.tar.bz2` | 7,0 GB | MD5SUMS del servidor |
| `mbdump-derived.tar.bz2` | 492 MB | MD5SUMS del servidor |
| 3 × `acousticbrainz-lowlevel-features-20220623-*.tar.zst` | 2,8 GB | `sha256sums` del servidor |
| `msd-mbid-2016-01-results-ab.csv.bz2` | 13 MB | no publicado; se valida abriendo el bz2 |

Total ~11 GB. Es reejecutable: lo que ya está y cuadra no se vuelve a bajar (revalidar los
11 GB cuesta ~3,5 min). Si un checksum falla, borra el archivo y sale con error. **Tarda
unos 40 min** con una conexión de ~4 MB/s, que es lo que da el mirror para el dump core.

**`01_extract.py`** (`make 01`) saca de los tarballs solo las 29 tablas del core y las 4 de derived a
`/data/interim`, y descomprime el mapeo MSD a `/data/interim/msd_mbid.csv`. **Tarda ~14
min**: 374 s el core, 13 s derived y el resto contando filas para el informe. Deja **21 GB**
de TSV.

Verificación (la imprime el propio script al terminar: 33 tablas, todas con filas > 0):

Para contar las columnas hay que entrar al contenedor, porque los TSV están dentro del
volumen:

```bash
make shell
```

Y ya dentro:

```bash
awk -F'\t' '{print NF; exit}' /data/interim/artist
awk -F'\t' '{print NF; exit}' /data/interim/recording
exit
```

Debe dar **19** y **9**, que es el número de columnas de esas tablas en el esquema de
MusicBrainz y lo que tendrá que reproducir el parser del DDL en la fase C.

Filas de las tablas grandes, por si hay que comparar tras un redump: `recording`
40.126.348 · `track` 57.777.221 · `url` 21.581.393 · `release_country` 13.266.453 ·
`l_release_url` 10.549.580 · `recording_tag` 7.302.510 · `artist` 2.980.329 ·
`msd_mbid.csv` 377.406.

### Fase C — Carga en DuckDB

```bash
make 02
make 03
```

**`02_headers.py`** (`make 02`) descarga `CreateTables.sql` del repo de MusicBrainz y saca
el orden de columnas de cada tabla (los TSV del dump no traen cabecera). El parser cuenta
paréntesis para no tropezar con los `CHECK (...)` multilínea. Deja
`/data/interim/headers.json` y **revienta con `assert` si `artist` no da 19 columnas o
`recording` 9**, que es la señal de que el DDL de `master` se desalineó con el dump.
Tarda segundos.

**`03_load_duckdb.py`** (`make 03`) carga los 21 GB de TSV como tablas materializadas en
`/data/mb.duckdb` (9,5 GB), más el mapeo MSD como `msd_mbid`. **Tarda ~16 min**; las
lentas son `track` (344 s) y `recording` (254 s). Corre con `memory_limit=2GB` y
`temp_directory` en el volumen, así que usa ~1 GB de RAM y derrama a disco. El propio
script imprime el `count(*)` de cada tabla: deben cuadrar con los números de la fase B.

Verificación manual:

```bash
make shell
```

Y dentro:

```bash
python -c "import duckdb; db = duckdb.connect('/data/mb.duckdb', read_only=True); print(db.execute('SELECT count(*) FROM recording').fetchone(), len(db.execute('DESCRIBE artist').fetchall()))"
```

Debe dar `(40126348,) 19`.

### Fase D — Matching MSD → recording MBID

_Pendiente._

### Fase E — Enriquecimiento

_Pendiente._

### Fase F — Exportación y entregables

_Pendiente._

## Limpiar contenedores (sin perder datos)

Los contenedores `etl_*` parados no ocupan casi nada, pero se acumulan. Para borrarlos:

```bash
make clean
```

Solo toca los `etl_*` de este proyecto, no los contenedores de otros. Y **no toca los
datos**: los 32 GB de `/data` están en el volumen `work`, que sobrevive a cualquier
borrado de contenedores. Borrar uno solo tira su capa de escritura y sus logs.

Para confirmar que los datos siguen ahí, `make shell` y dentro `du -sh /data/raw
/data/interim`.

## Cómo borrar todo

> **Cuidado:** el siguiente comando sí destruye datos, y no hay deshacer. Elimina el
> volumen `work` con los ~32 GB de dumps crudos, los TSV y la base DuckDB. Recuperarlos
> significa repetir las fases B en adelante: ~40 min de descarga más ~14 min de extracción.

```bash
make nuke      # pide escribir SI para confirmar
```

**Sobrevive** todo lo que está en el repo: el código, `data/grupo_5.csv`,
`data/processed/` y `docs/`.

Comprobado: tras el borrado, listar `/data` en un contenedor nuevo devuelve un directorio
vacío y `data/processed/` en el host queda intacto.
