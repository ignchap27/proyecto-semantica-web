# Bitácora

Qué se intentó, qué falló y los números medidos, sesión a sesión.

## Etapa 2 · Fase G — Competency questions y revisión del modelo (2026-10-11)

**Producto elegido:** un explorador musical (filtrar por sello, género y época; saltar
entre artistas que comparten miembros; comparar tempo y modo entre géneros y sellos).

**Primero, mirar qué hay en el dump** (DuckDB, antes de escribir ninguna CQ de navegación):
- `l_artist_artist` sí está. Contando solo pares con los dos artistas en nuestro dataset:
  2.764 `member of band` (2.031 miembros, 1.855 grupos), ~105 `married`, ~107 `parent`,
  y apenas **83 `collaboration`**. La pregunta tipo "¿quién colaboró con X?" no da: se
  cambió por "grupos que comparten miembros", que se recorre con `(^miembroDe/miembroDe)+`.
- **`l_genre_genre` no existe**: en la Etapa 1 no se extrajo. Sin jerarquía de géneros
  no hay CQ de subgéneros. La jerarquía del modelo será la de tipos de artista.
- `genre` (vocabulario oficial de MB) tiene 2.197 géneros. Los tags de artista mezclan
  géneros con cosas como "1970s"; filtrando contra `genre` quedan 978 géneros en 14.490
  de los 26.884 artistas.
- Tipos de artista: 13.562 Group, 12.244 Person, 969 sin tipo, 64 Orchestra, 20 Choir,
  15 Character, 10 Other.

**Respuestas esperadas** con `scripts/cq_esperadas.py` (`make cq`, ~3 s).

Lo que falló o hubo que corregir:
- La CQ8 sacaba `[no label]` en el top 10 (555 canciones). Es el "sello" que usa MB para
  autoediciones, no un sello real. Se excluye ya en el script; en la fase I no debe
  generar un `:Sello`.
- Para la CQ4 cogí primero el grupo con más miembros (Fania All-Stars, 13): solo conecta
  con 1 grupo, una respuesta que no enseña nada. Con **Deep Purple** salen 219 grupos
  alcanzables (13 directos), que es lo que una navegación transitiva debe mostrar.
- Aparecen 228 canciones con año 2020+: el MSD es de 2010, así que son años de
  reediciones que trajo MusicBrainz al rellenar el `year=0`. Se deja anotado; no es un
  error del script.
- `README.md` listaba `docs/bitacora.md` e `informe.md`, pero se borraron en el commit
  del informe final de la Etapa 1. Esta bitácora empieza de nuevo.

Números clave: CQ1 = 79, CQ2 = 2.849, CQ3 = 2.764 pares, CQ4 = 219, CQ5 = 12 sellos,
CQ7 = 78.897 canciones con año. Detalle en `docs/competency_questions.md`.
