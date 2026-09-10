# Etapa 1 — Extracción y enriquecimiento de información musical

Ignacio Chaparro · Web Semántica (MISIS) · Grupo 5

> Documento en construcción. Cada sección se redacta en la fase que le corresponde; en la
> fase F se recorta a 4 páginas y se pule. La materia prima está en `bitacora.md`.

## 1. Fuentes utilizadas

_Fase B._

## 2. Proceso de extracción

_Fases B–C._

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
