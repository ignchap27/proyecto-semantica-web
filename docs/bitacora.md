# Bitácora

Registro cronológico de decisiones, problemas y números medidos. Es el borrador del que
se destila `informe.md`. Una entrada por sesión.

---

## 2026-09-10 — Fase A: exploración del dataset y andamiaje

### Qué se hizo

Inspección del CSV de entrada, elección de fuentes y montaje del entorno Docker.

### Hallazgos sobre `data/grupo_5.csv`

100.000 filas, 7 columnas, sin valores vacíos salvo un `title`.

| Columna | Observación |
|---|---|
| `track_id` | 100.000 únicos |
| `artist_mbid` | **100 % presente y con formato UUID válido**, 27.352 artistas distintos |
| `artist_name` | 31.788 valores distintos (más nombres que MBIDs: hay variantes de nombre para un mismo artista) |
| `release` | 61.385 valores distintos |
| `year` | **45.219 filas (45,2 %) valen `0`** — sentinela del MSD para año desconocido |
| `duration` | en segundos, float |

Que el `artist_mbid` esté completo cambia la estrategia: la reconciliación de artista está
resuelta de entrada y el problema se reduce a `track_id` → **recording** MBID.

### Decisiones de arquitectura

**Descartada la API de MusicBrainz.** El límite es 1 petición/segundo → ~28 horas solo
para resolver recordings. Se va con dumps locales.

**Descartado Postgres, elegido DuckDB.** El dump core son TSV planos; DuckDB los lee
directamente con `read_csv` sin importar nada. Postgres exigiría importar ~45 GB (varias
horas) para el mismo resultado.

**Descartado el mapeo MSD→MBID como ruta principal.** El mapeo de AcousticBrainz labs
(`msd-mbid-2016-01`) cubre ~250.000 de los 1.000.000 de ids del MSD. Nuestras 100.000 son
un subconjunto, así que se espera ~25 % de cobertura: insuficiente. Queda como medida
independiente de precisión del matching propio.

**Ruta principal elegida:** acotar los recordings candidatos por `artist_mbid` y decidir
con título normalizado + duración. Con 27.352 artistas el conjunto candidato por fila es
de decenas, así que no hace falta fuzzy matching global.

### Problemas encontrados

**El PDF del enunciado no se podía leer.** No hay `pdftotext` ni `poppler` en la máquina y
el PDF usa fuentes subconjunto con codificación por nombres de glifo. Hubo que escribir un
extractor que decodifica el array `/Differences` de cada fuente y filtra los streams de
imagen. Anecdótico, pero costó un rato.

**Los tags no están donde se esperaba.** La tabla `genre` de MusicBrainz sí está en el
dump core, pero es solo el vocabulario de géneros: la asociación entidad↔género vive en
`artist_tag`, `recording_tag` y `release_group_tag`, que están en **`mbdump-derived`**
(492 MB aparte). Verificado contra `CORE_TABLE_LIST` y `DERIVED_TABLE_LIST` en
`lib/MusicBrainz/Server/Constants.pm` del repo de musicbrainz-server. Como el enunciado
pide géneros explícitamente, derived pasó de opcional a obligatorio.

**Los TSV del dump no traen cabecera.** El orden de columnas hay que sacarlo de
`admin/sql/CreateTables.sql`. Al probar el parseo apareció una trampa: un parser
línea-a-línea produce columnas duplicadas en `artist` y `link`, porque los bloques
`CHECK (...)` multilínea contienen nombres de columna que parecen declaraciones. Hay que
llevar conteo de paréntesis. Referencia para verificar: `artist` = 20 columnas terminando
en `begin_area, end_area`; `recording` = 9.

**Dumps de AcousticBrainz: el obvio es el equivocado.** Los dumps JSON son 30 archivos de
1–2 GB cada uno. Existe un conjunto mucho más pequeño,
`acousticbrainz-lowlevel-features-20220623` (3 archivos, ~2,8 GB en total) con las
features ya tabuladas, que es lo que realmente necesitamos.

### Estado del entorno

- Disco libre en el host: 208 GB. Presupuesto del proyecto: ~32 GB.
- Docker 29.1.3, Compose v2.40.3.
- Último fullexport de MusicBrainz disponible al momento: `20260909-002431`. El script de
  descarga resuelve `fullexport/LATEST` en vez de quemar la fecha.

### Resultado de la fase A

Imagen construida en ~1 min. Dentro del contenedor: DuckDB 1.5.5, pandas 2.3.3,
rapidfuzz 3.14.6, más `lbzip2`, `zstd` y `curl`. El CSV de entrada se lee desde
`/app/data/grupo_5.csv` y devuelve las 100.000 filas.

Verificado también el ciclo de borrado: tras `docker compose down -v` el volumen `work`
desaparece y `/data` vuelve vacío en la siguiente ejecución, mientras que
`data/processed/` y el código del host quedan intactos. En macOS los archivos que el
contenedor escribe en los bind mounts aparecen en el host con el usuario correcto, así
que no hay problema de permisos con los entregables.

### Pendiente para la fase B

Descargar y extraer solo las ~34 tablas necesarias (de las 236 del core), en streaming
sobre el tar para no materializar los 45 GB completos.
