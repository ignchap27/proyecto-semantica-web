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
```

## Requisitos

Solo **Docker**. Nada se instala en la máquina anfitriona.

Espacio en disco: ~7,5 GB de descargas + ~25 GB de TSV extraídos.

```bash
docker compose build
```

## Cómo replicar el ETL

Los scripts se corren de uno en uno, en orden. Cada fase deja su salida lista para la
siguiente.

### Fase A — Andamiaje

Construye la imagen y comprueba que las dependencias y el dataset de entrada están dentro
del contenedor.

```bash
docker compose build
docker compose run --rm etl python -c "import duckdb, pandas, rapidfuzz, unidecode; print('ok')"
docker compose run --rm etl bash -c "which lbzip2 zstd curl"
```

Tarda ~1 min construyendo la imagen desde cero. Versiones verificadas: DuckDB 1.5.5,
pandas 2.3.3, rapidfuzz 3.14.6.

Para comprobar que el dataset de entrada está montado y completo:

```bash
docker compose run --rm etl python -c "import const; print(sum(1 for _ in open(const.SONGS_CSV)) - 1)"
```

Debe imprimir `100000`.

### Fase B — Descarga y extracción

_Pendiente._

### Fase C — Carga en DuckDB

_Pendiente._

### Fase D — Matching MSD → recording MBID

_Pendiente._

### Fase E — Enriquecimiento

_Pendiente._

### Fase F — Exportación y entregables

_Pendiente._

## Cómo borrar todo

```bash
docker compose down -v
```

Elimina el contenedor y el volumen `work` con los ~30 GB de dumps crudos y la base DuckDB.

**Sobrevive** todo lo que está en el repo: el código, `data/grupo_5.csv`,
`data/processed/` y `docs/`. Para volver al estado inicial basta con repetir las fases
desde la B.

Comprobado: tras `down -v`, `docker compose run --rm etl ls /data` devuelve un directorio
vacío y `data/processed/` en el host queda intacto.
