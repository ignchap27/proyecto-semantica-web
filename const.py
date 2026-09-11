"""Rutas, URLs y listas de tablas. Todo lo configurable del proyecto vive aqui."""

# --- rutas (dentro del contenedor) ---
SONGS_CSV = "/app/data/grupo_5.csv"
PROCESSED = "/app/data/processed"

RAW = "/data/raw"          # descargas
INTERIM = "/data/interim"  # TSV extraidos del dump
DUCKDB = "/data/mb.duckdb"

# --- fuentes ---
METABRAINZ = "https://data.metabrainz.org/pub/musicbrainz"

# el directorio del dump cambia cada semana: 00_download.py lee este archivo
# para saber cual es el ultimo en vez de tenerlo quemado aqui
MB_LATEST_URL = f"{METABRAINZ}/data/fullexport/LATEST"
MB_FULLEXPORT = f"{METABRAINZ}/data/fullexport"

MB_CORE_FILE = "mbdump.tar.bz2"
MB_DERIVED_FILE = "mbdump-derived.tar.bz2"
MB_MD5SUMS = "MD5SUMS"

AB_FEATURES = f"{METABRAINZ}/acousticbrainz/dumps/acousticbrainz-lowlevel-features-20220623"
AB_SHA256SUMS = "sha256sums"
AB_FEATURE_FILES = [
    "acousticbrainz-lowlevel-features-20220623-lowlevel.tar.zst",
    "acousticbrainz-lowlevel-features-20220623-rhythm.tar.zst",
    "acousticbrainz-lowlevel-features-20220623-tonal.tar.zst",
]

# mapeo MSD -> MBID de AcousticBrainz labs. Solo cubre ~25% de nuestras filas,
# asi que sirve para validar el matching, no como fuente principal.
MSD_MAP_URL = (
    f"{METABRAINZ}/acousticbrainz/acousticbrainz-labs/download/msdtombid/"
    "msd-mbid-2016-01-results-ab.csv.bz2"
)

# DDL de donde salen las cabeceras: los TSV del dump vienen sin nombres de columna
CREATE_TABLES_SQL = (
    "https://raw.githubusercontent.com/metabrainz/musicbrainz-server/master/"
    "admin/sql/CreateTables.sql"
)

# --- tablas a extraer ---
# el dump core trae 236 tablas y ~45 GB; solo sacamos estas
MB_CORE_TABLES = [
    "area",
    "artist",
    "artist_alias",
    "artist_credit",
    "artist_credit_name",
    "artist_gid_redirect",
    "artist_type",
    "gender",
    "genre",
    "l_artist_artist",
    "l_artist_url",
    "l_recording_work",
    "l_release_group_url",
    "l_release_url",
    "label",
    "language",
    "link",
    "link_type",
    "medium",
    "recording",
    "recording_gid_redirect",
    "release",
    "release_country",
    "release_group",
    "release_group_primary_type",
    "release_label",
    "script",
    "track",
    "url",
    "work",
]

# los tags (y con ellos los generos por entidad) NO estan en el dump core
MB_DERIVED_TABLES = [
    "tag",
    "artist_tag",
    "recording_tag",
    "release_group_tag",
]
