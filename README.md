# Proyecto de Semántica Web — Etapa 1

Ignacio Chaparro

Nos dieron `data/grupo_5.csv`: 100.000 canciones del Million Song Dataset con 7 columnas
(id, título, artista, álbum, año, duración y el MBID del artista). La tarea es
enriquecerlas con fuentes externas, cruzando cada canción con las entidades reales de esas
fuentes. Al final se entregan CSVs consolidados, un modelo conceptual, un informe de 4
páginas y este código.

Las fuentes son dumps completos, no APIs (la API de MusicBrainz permite 1 petición por
segundo: resolver 100.000 canciones tardaría ~28 horas):

- **MusicBrainz core** (7 GB): grabaciones, álbumes, artistas, sellos, URLs externas.
- **MusicBrainz derived** (492 MB): tags y géneros por entidad.
- **AcousticBrainz** (2,8 GB): tempo, tonalidad, sonoridad y demás features de audio.
- **Mapeo MSD→MBID** (13 MB): para validar nuestro propio matching.

## Qué necesita la máquina

- **Docker y `make`.** Nada más. Todo corre dentro de un contenedor; en la máquina no se
  instala ni Python ni ninguna librería.
- **~45 GB de disco libres.** Los dumps descargados ocupan 11 GB, los TSV extraídos 21 GB
  y la base DuckDB 9,5 GB. Todo eso vive en un volumen de Docker, no en el repo.
- **4 GB de RAM bastan.** La carga en DuckDB está limitada a 2 GB de memoria y derrama a
  disco lo que no cabe (sin ese límite, la carga se comía toda la RAM de la máquina).
- **Conexión decente.** Son 11 GB de descarga; el mirror da unos 4 MB/s, así que la
  descarga tarda ~40 min haga lo que haga tu conexión.

## Cómo se corre: el Makefile

Un `Makefile` es un archivo donde se guardan comandos largos bajo nombres cortos, se usan
escribiendo `make <nombre>`. Aquí lo usamos porque cada paso del ETL eran cuatro comandos
de Docker (crear contenedor, correrlo, seguir los logs, esperar el código de salida) y era
fácil equivocarse. Con el Makefile nadie tiene que escribir Docker a mano.

| Comando | Qué hace |
|---|---|
| `make check` | comprueba que el entorno está bien: construye la imagen si hace falta, lista las librerías y verifica que el CSV de entrada tiene 100.001 líneas |
| `make 00`, `make 01`, … | corre un paso del ETL y muestra su salida en vivo |
| `make all` | corre todos los pasos que existan, en orden |
| `make logs-00` | vuelve a mostrar los logs de un paso que ya corrió |
| `make shell` | abre un bash dentro del contenedor, para mirar `/data` |
| `make build` | construye la imagen de Docker (opcional: los demás comandos la construyen solos) |
| `make clean` | borra los contenedores parados de este proyecto; **no borra datos** |
| `make nuke` | borra el volumen con los ~42 GB de datos; pide confirmación |

Dos detalles útiles:

- Los pasos salen de los nombres de archivo en `scripts/`: si mañana aparece
  `scripts/04_match.py`, existe `make 04` sin tocar el Makefile.
- Cada paso corre en segundo plano. **Ctrl-C corta la pantalla, no el proceso**: la
  descarga sigue, y te reenganchas con `make logs-00`. Si relanzas un paso que aún corre,
  verás `container name is already in use`; es la señal de que sigue vivo, no un error.

## Las fases

Se trabaja por fases, en orden. Cada script imprime al final sus propios números de
verificación.

### Fase A — Entorno

Dockerfile, docker-compose y Makefile. Para comprobarla:

```bash
make check
```

Tiene que imprimir las versiones de duckdb/pandas/rapidfuzz/unidecode, las rutas de
`curl`, `lbzip2` y `zstd`, y `100001 data/grupo_5.csv`.

### Fase B — Descargar y extraer los dumps

```bash
make 00     # descarga los 11 GB y verifica checksums (~40 min)
make 01     # extrae las 34 tablas que usamos a /data/interim (~14 min)
```

El paso 00 es reejecutable: lo ya descargado y verificado no se vuelve a bajar. Si un
checksum no cuadra, borra el archivo y falla, para que un dump corrupto no llegue más
lejos. El paso 01 saca solo las tablas que nos interesan (34 de 236) sin materializar
nunca los 45 GB del dump completo.

Para verificar, además de los conteos que imprime el script: dentro de `make shell`,
`awk -F'\t' '{print NF; exit}' /data/interim/artist` debe dar **19** y lo mismo sobre
`recording` debe dar **9** (los TSV no traen cabecera; esos son los números de columnas
del esquema oficial).

### Fase C — Cargar todo en DuckDB

```bash
make 02     # saca los nombres de columna del DDL oficial (segundos)
make 03     # carga los TSV en /data/mb.duckdb (~16 min)
```

El paso 02 falla a propósito si `artist` no da 19 columnas o `recording` 9: significaría
que el esquema publicado ya no cuadra con el dump. El paso 03 imprime el `count(*)` de
cada tabla; deben coincidir con los de la fase B. Para verificar a mano, dentro de
`make shell`:

```bash
python -c "import duckdb; db = duckdb.connect('/data/mb.duckdb', read_only=True); print(db.execute('SELECT count(*) FROM recording').fetchone(), len(db.execute('DESCRIBE artist').fetchall()))"
```

Debe dar `(40126348,) 19` (con el dump `20260909-002431`; otro dump dará otro conteo).

### Fase D — Matching canción → grabación

```bash
make 04     # asigna a cada canción su MBID de grabación (~1 min)
```

Es el paso central del proyecto: cruza cada una de las 100.000 canciones con la grabación
(recording) que le corresponde en MusicBrainz. Como el MBID del artista viene en el CSV de
entrada, el script solo compara cada canción contra las grabaciones de su propio artista
(unos cientos por canción, no 40 millones), en tres pasadas: título normalizado igual,
título sin el sufijo entre paréntesis ("(Album Version)" y compañía), y similitud difusa
para lo que queda. Los empates se resuelven prefiriendo duración parecida y la grabación
más referenciada.

Debe imprimir una cobertura de ~80 % (80.719 de 100.000 con el dump `20260909-002431`) y
dejar `data/processed/matches.csv` con una fila por canción resuelta. Al final contrasta
contra el mapeo MSD→MBID de AcousticBrainz, que cubre ~39.500 de nuestras filas: el
acuerdo debe rondar el 57 % exacto y el 83 % "laxo" (mismo título y mismo artista pero
distinto MBID: son grabaciones duplicadas sin fusionar en MusicBrainz, no errores).

Para verificarlo hay un script de comprobación que revienta si algo no cuadra
(cobertura < 60 %, ids duplicados, MBIDs inexistentes o acuerdo laxo < 75 %). No es un
paso del ETL, así que se corre dentro de `make shell`:

```bash
python scripts/test_match.py
```

### Fase E — Enriquecimiento

```bash
make 05     # artistas, ediciones, sellos, tags y urls desde MusicBrainz (~15 s)
make 06     # features acústicas desde AcousticBrainz (~4 min)
```

El paso 05 toma los 80.719 matches de la fase D y saca de la base de MusicBrainz cinco
CSVs a `data/processed/`, cada uno con una columna `fuente` que dice de dónde salió el
dato (la "procedencia" que pide el enunciado):

| Archivo | Filas | Qué trae |
|---|---|---|
| `artists.csv` | 26.884 | nombre, tipo, género, país, años de actividad, top 5 de tags y enlace a Wikidata por artista |
| `releases.csv` | 80.706 | la edición (release) más antigua de cada grabación, con año, país y tipo de álbum |
| `labels.csv` | 56.509 | sello discográfico y número de catálogo de esas ediciones |
| `tags.csv` | 285.855 | tags de la comunidad por grabación y por grupo de ediciones |
| `urls.csv` | 499.891 | todos los enlaces externos (Wikidata, Discogs, YouTube…) de artistas y ediciones |

Para elegir "la" edición de cada grabación (una grabación suele estar en muchos discos)
se toma la de fecha más antigua, prefiriendo las oficiales sobre bootlegs y promos. Solo
13 grabaciones se quedan sin edición (grabaciones "sueltas" en MusicBrainz).

El paso 06 extrae los tres `tar.zst` de AcousticBrainz (descargados en la fase B),
cruza sus ~29 M de filas por categoría con nuestros MBIDs —canonicalizando por
`recording_gid_redirect`, porque los MBIDs de AcousticBrainz son de 2022— y deja
`features.csv` con bpm, tonalidad, danceability y compañía. AcousticBrainz se congeló
en 2022, así que no cubre todo: 45.211 de los 80.719 matches (56 %) tienen features.
Al terminar borra los CSVs extraídos (los `tar.zst` originales quedan en `/data/raw`).

Verificación: los seis CSVs existen en `data/processed/` y los conteos de arriba salen
en `make logs-05` / `make logs-06`. Ambos scripts revientan solos si hay ids duplicados
o algún CSV queda vacío.

### Fase F — Exportar entregables

_Pendiente._

## Borrar cosas

`make clean` borra solo contenedores parados; los datos están en un volumen aparte y no
los toca. Lo único que borra los ~42 GB es:

```bash
make nuke   # pide escribir SI
```

No hay deshacer: recuperar los datos es repetir desde `make 00` (~70 min entre descarga y
carga). El código, el CSV de entrada, `data/processed/` y `docs/` viven en el repo y
sobreviven siempre.

## Estructura del repo

```
.
├── Makefile                # los comandos de arriba
├── Dockerfile              # python:3.12-slim + curl, lbzip2, zstd
├── docker-compose.yml      # un servicio (etl) + volumen `work` para los datos pesados
├── requirements.txt        # duckdb, pandas, rapidfuzz, unidecode
├── const.py                # rutas, URLs y listas de tablas
├── data/
│   ├── grupo_5.csv         # entrada (no se toca)
│   └── processed/          # CSVs finales
├── docs/
│   ├── bitacora.md         # qué se hizo, qué falló y los números medidos
│   ├── informe.md          # el entregable de 4 páginas, se escribe en paralelo
│   └── modelo_conceptual.md
└── scripts/                # un script por paso, sin frameworks
    ├── 00_download.py
    ├── 01_extract.py
    ├── 02_headers.py
    ├── 03_load_duckdb.py
    ├── 04_match.py
    ├── 05_enrich.py
    ├── 06_acousticbrainz.py
    └── test_match.py       # checks de la fase D, se corre dentro de make shell
```
