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

---

## 2026-09-10 — Fase B: descarga y extracción de los dumps

### Qué se hizo

`scripts/00_download.py` (descarga + verificación de checksums) y `scripts/01_extract.py`
(extracción selectiva de tablas). Resultado: 33 tablas en TSV en `/data/interim` más el
mapeo MSD→MBID.

### Números medidos

| | |
|---|---|
| Versión del dump | `20260909-002431` (resuelta vía `fullexport/LATEST`) |
| Descargado | 11 GB — core 7,0 GB, derived 492 MB, AB lowlevel 2,8 GB, mapeo MSD 13 MB |
| Tiempo de descarga | ~40 min (el mirror da ~4 MB/s para el core; los archivos de AB bajan a ~10 MB/s) |
| Revalidación de checksums | 3,5 min para los 11 GB |
| Extracción core (29 tablas) | 374 s |
| Extracción derived (4 tablas) | 13 s |
| TSV resultantes | 21 GB |
| Total en el volumen `work` | 32 GB |

Tablas grandes: `track` 57.777.221 filas (7,8 GB) · `recording` 40.126.348 (4,6 GB) ·
`url` 21.581.393 (2,6 GB) · `release_country` 13.266.453 · `l_release_url` 10.549.580 ·
`l_recording_work` 7.869.911 · `artist_credit_name` 7.186.104 · `recording_tag` 7.302.510
· `medium` 6.326.219 · `release` 5.763.531 · `release_group_tag` 5.011.678 · `artist`
2.980.329.

El mapeo `msd-mbid-2016-01` tiene **377.406 filas**, no las ~250.000 que se estimaron en la
fase A. Sobre 1.000.000 de ids del MSD sigue siendo un 38 %; la cobertura real sobre
nuestras 100.000 se mide en la fase D.

### Problemas encontrados

**El mirror se cuelga a mitad de descarga.** La primera corrida se quedó pegada en el
tercer archivo de AcousticBrainz: 26 MB en 40 minutos, sin error, sin cortar la conexión.
Hubo que matarla. Se le añadieron a `curl` `--speed-limit 10240 --speed-time 60` (si baja
de 10 kB/s durante un minuto, aborta) más `--retry 10 --retry-all-errors`, que con `-C -`
retoma donde iba.

**Reanudar una descarga colgada da un archivo corrupto.** Al reintentar, `curl -C -`
retomó desde el byte 28.749.824 y el resultado no cuadró con el SHA-256 publicado. Que el
script verifique *después* de descargar y borre el archivo malo es justo lo que salvó la
situación: el fallo se vio en 3 minutos y no dos fases más tarde, con la extracción
reventando por un tar truncado. La segunda descarga, ya completa, cuadró.

**`TIMESTAMP` no está donde parecía.** Se intentó extraer del tar del core para dejar
constancia de la fecha del dump, pero vive en la raíz del tarball, no dentro de `mbdump/`,
así que `--strip-components=1` se lo comía y `tar` salía con código 2 tras haber extraído
correctamente las 29 tablas. Se quitó de la lista: la procedencia ya queda registrada en
`/data/raw/MB_VERSION.txt`, que escribe `00_download.py` con la versión que resolvió.

**`artist` tiene 19 columnas, no 20.** El dato apuntado en la fase A estaba mal. Verificado
por partida doble: el `CREATE TABLE artist` del DDL declara 19 columnas (`id` … `end_area`)
y los TSV dan 19 campos en las 200.000 primeras filas. `recording` sí son 9. Corregido en
`CLAUDE.md` porque la fase C usa ese número como prueba del parser del DDL.

### Decisiones

**Descargar a disco en vez de extraer en streaming desde la URL.** Era tentador encadenar
`curl | lbzip2 -dc | tar -x` y ahorrarse los 11 GB de tarballs, pero entonces cualquier
corte de red obliga a rebajar 7 GB, no hay contra qué comparar el checksum y re-extraer una
tabla que se olvidó exige repetir la descarga entera. Con lo frágil que resultó ser el
mirror, fue la decisión correcta.

**Los tarballs se conservan tras extraer.** Ocupan 11 GB, pero re-descargarlos cuesta 40
minutos y `docker compose down -v` los borra igual.

**Los dumps de AcousticBrainz se bajan ahora y se extraen en la fase E.** Están verificados
y en disco; su formato interno se resuelve cuando toque.

### Pendiente para la fase C

Parsear `CreateTables.sql` contando paréntesis para sacar las cabeceras (prueba: `artist` =
19, `recording` = 9) y cargar los TSV en DuckDB.

## 2026-09-10 — Interludio: un `Makefile` para no escribir Docker a mano

Los comandos de cada paso eran cuatro líneas de Docker (`rm`, `run -d --name`, `logs -f`,
`wait`) y el README estaba lleno de ellas. Sustituidos por un `Makefile`: `make 00`,
`make 01`, `make all`, más `check`, `shell`, `logs-XX`, `clean` y `nuke`.

La lista de pasos no está quemada: sale de `ls scripts/[0-9][0-9]_*.py`, así que al crear
`scripts/02_headers.py` aparece `make 02` y entra en `make all` sin tocar nada. `make all`
lleva `.NOTPARALLEL` porque cada paso depende del anterior y un `-j` accidental los
solaparía.

Se conserva lo que ya funcionaba: contenedor con nombre, sin `--rm`, en segundo plano con
`-d`, para que Ctrl-C corte el seguimiento de los logs y no el proceso. El `make` termina
con `exit $(docker wait ...)`, así que un paso fallido rompe la cadena de `make all` en vez
de seguir con datos a medias.

**Detalle deliberado:** el borrado previo del contenedor usa `docker rm`, no `docker rm
-f`. Con `-f` un `make 00` distraído mataría una descarga de 40 minutos en curso; sin `-f`
el borrado falla, `compose` responde `container name is already in use` y el proceso sigue
vivo. El error feo es la protección.

Verificado: `make check` imprime las cuatro dependencias, los tres binarios y `100001
data/grupo_5.csv`; `make 00` completo (revalidación de los 11 GB, 2 min 38 s) salió con
código 0; `make clean` borró los `etl_*` y dejó intactos los contenedores de otros
proyectos de la máquina.

---

## 2026-09-10 — Auditoría de código + Fase C: cabeceras y carga en DuckDB

### Auditoría

Se revisó todo el código existente buscando complejidad que recortar. Veredicto: ya era
mínimo; solo cayeron `DURATION_TOLERANCE_S` y `FUZZY_THRESHOLD` de `const.py` (nadie las
usaba; vuelven en la fase D cuando exista el matching) y se corrigió en `CLAUDE.md` un "20
columnas" que había quedado de la fase A (son 19).

### Qué se hizo

`scripts/02_headers.py` (parsea `CreateTables.sql` → `headers.json`) y
`scripts/03_load_duckdb.py` (carga los TSV como tablas en `/data/mb.duckdb`).

### Números medidos

| | |
|---|---|
| `make 02` | segundos; 34 tablas, `artist` = 19 columnas, `recording` = 9 |
| `make 03` | ~16 min total; `track` 344 s, `recording` 254 s, `url` 60 s |
| Base resultante | `/data/mb.duckdb`, 9,5 GB (los 21 GB de TSV comprimen a menos de la mitad) |
| RAM durante la carga | ~1 GB estable tras el ajuste (ver abajo) |

Los `count(*)` cuadran uno a uno con los `wc -l` de la fase B. `msd_mbid` da 377.405
filas (377.406 líneas menos la cabecera).

### Problemas encontrados

**La primera carga se comió toda la RAM del computador.** DuckDB por defecto reclama
hasta el 80 % de la memoria disponible y, con `preserve_insertion_order` activo (el
default), bufferea la tabla entera antes de escribirla: con `recording` (4,6 GB) y
`track` (7,8 GB) eso satura la máquina. Hubo que matar la carga. Arreglo: tres `SET` al
abrir la conexión — `memory_limit='2GB'`, `preserve_insertion_order=false` y
`temp_directory` dentro del volumen `work` para que lo que no quepa derrame a disco.
Con eso el contenedor se quedó en ~1 GB de RAM y la carga completa tardó ~16 min.

**El parser del DDL salió a la primera.** La regla "línea a profundidad 1 que empieza en
minúscula = columna" esquiva sola los `CHECK (...)` multilínea, porque sus líneas quedan
a profundidad > 1 y las palabras clave van en mayúsculas. Los `assert` de 19/9 columnas
pasaron contra el `master` actual; si un futuro cambio de esquema los rompe, el paso 02
revienta ahí y no en silencio en la fase D.

**Tipos inferidos con el archivo completo.** `read_csv` con la muestra por defecto
arriesga inferir mal una columna casi-numérica y reventar a mitad de carga; se usa
`sample_size=-1` (dos pasadas). Es la mitad del coste de los 16 min y se paga una sola
vez.

### Pendiente para la fase D

Matching `track_id` → recording MBID: candidatos por `artist_mbid`, decisión por título
normalizado + duración. Probar primero con muestra de 1.000.

---

## 2026-09-10 — Fase D: matching `track_id` → recording MBID

### Qué se hizo

`scripts/04_match.py` (el matching en cascada) y `scripts/test_match.py` (los checks).
La estrategia decidida en la fase A funcionó: candidatos acotados por `artist_mbid` y
decisión por título normalizado + duración, en tres pasadas sobre lo aún sin resolver.

### Números medidos

| | |
|---|---|
| Cobertura total | **80.719 / 100.000 = 80,7 %** (el criterio era ≥ 60 %) |
| Por método | exacto 66.446 · sin sufijo 8.970 · fuzzy 5.303 |
| Artistas resueltos | 26.242 directos + 642 por `artist_gid_redirect`; 468 sin resolver |
| Candidatos | 8,6 M recordings para los 26.884 artistas |
| Tiempo total | **40 s** (el fuzzy, la parte "lenta", tarda 12 s sobre 23.588 pendientes) |
| Contraste AB | el mapeo cubre 39.513 de nuestras filas (39,5 %, no el 25 % estimado) |
| Acuerdo con AB | exacto 57,5 %, laxo 82,9 % (ver abajo) |

Con la muestra de 1.000 los números fueron casi idénticos (80–81 % de cobertura), así que
la corrida completa no dio sorpresas.

### Problemas encontrados

**`msd_mbid` estaba mal cargada desde la fase C.** El CSV del mapeo no trae cabecera,
pero `read_csv` sin `names=` decidió que la primera fila (toda VARCHAR) era la cabecera:
la tabla quedó con un track id como nombre de columna y una fila menos. Por eso la fase C
contó 377.405 filas "menos la cabecera": no había cabecera, son 377.406. Corregido en
`03_load_duckdb.py` y recargada la tabla en el paso 04 (13 MB, instantáneo) para no
repetir los 16 minutos de la carga completa.

**El acuerdo con AB salió al 41 % y no era un error nuestro.** Alarmante a primera vista.
Diagnóstico sobre la muestra: de 247 desacuerdos, 200 eran mismo título normalizado y 218
mismo `artist_credit` — MusicBrainz está lleno de grabaciones duplicadas sin fusionar
(misma canción, distinto MBID), y nosotros elegíamos un duplicado y el mapeo de AB otro.
Dos arreglos: (1) desempatar prefiriendo la grabación más referenciada por `track` (la
"canónica"), lo que subió el acuerdo exacto de 41 % a 57,5 %; (2) medir también un
"acuerdo laxo" (mismo título normalizado + mismo `artist_credit`) que da 82,9 % y es la
métrica honesta — el resto del desacuerdo es en buena parte atribuible al propio mapeo de
AB, que también se generó por matching automático en 2016.

**Lo que salió a la primera:** el parser de títulos en SQL puro (macro con
`strip_accents` + `regexp_replace`), la resolución por `artist_gid_redirect` y la
cascada con `NOT IN (SELECT track_id FROM match)`.

### Decisiones

- **Popularidad como desempate.** Entre candidatos con el mismo título, gana el que tenga
  la duración dentro de ±15 s, luego el más referenciado por `track`, luego la menor
  diferencia de duración. Además de subir el acuerdo con AB, elegir el duplicado canónico
  mejora las probabilidades de encontrar features en AcousticBrainz en la fase E.
- **El fuzzy lleva guardia de duración** (±15 s, `token_set_ratio` ≥ 90): sin ella
  empareja títulos parecidos de canciones distintas. Grabaciones sin `length` quedan
  fuera del fuzzy.
- **El 19,3 % sin match se queda sin match.** Bajar el umbral del fuzzy compraría
  cobertura pagando con falsos positivos; 80,7 % ya dobla el criterio de la fase.

### Pendiente para la fase E

Enriquecimiento: artistas/releases/labels/tags/urls desde MusicBrainz y features desde
los dumps de AcousticBrainz (extraerlos primero; están descargados desde la fase B).
