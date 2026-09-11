# Atajos del ETL. Todo corre en Docker; nada se instala en el host.
#
#   make 00      un paso suelto        make all     todos en orden
#   make check   verifica el entorno   make shell   bash dentro del contenedor
#   make logs-00 relee logs de un paso make clean   borra contenedores parados

# los pasos salen de scripts/, asi que un script nuevo aparece solo
STEPS := $(shell ls scripts/[0-9][0-9]_*.py 2>/dev/null | sed 's|.*/\([0-9][0-9]\)_.*|\1|')

.PHONY: all build check shell clean nuke $(STEPS)
.NOTPARALLEL:   # los pasos dependen del anterior; nunca en paralelo

all: $(STEPS)

build:
	docker compose build

# Contenedor con nombre y en segundo plano: Ctrl-C corta el seguimiento de los
# logs, no el proceso. Si el paso ya corre, el `docker rm` falla y compose avisa
# de que el nombre esta en uso, que es justo lo que queremos.
$(STEPS):
	@docker rm etl_$@ >/dev/null 2>&1 || true
	@docker compose run -d --name etl_$@ etl python scripts/$@_*.py >/dev/null
	@docker logs -f etl_$@
	@code=$$(docker wait etl_$@); echo "--- etl_$@ salio con codigo $$code"; exit $$code

logs-%:
	@docker logs -f etl_$*

check:
	@docker rm etl_check >/dev/null 2>&1 || true
	@docker compose run --name etl_check etl bash -c '\
		pip list | grep -Ei "duckdb|pandas|rapidfuzz|unidecode" && \
		which curl lbzip2 zstd && \
		wc -l data/grupo_5.csv'

shell:
	@docker rm etl_shell >/dev/null 2>&1 || true
	docker compose run --name etl_shell etl bash

clean:
	-@docker rm $$(docker ps -aq -f 'name=^etl_') 2>/dev/null || true

# borra el volumen `work`: los ~42 GB de dumps, TSV y la base duckdb
nuke:
	@read -p "Borra los ~42 GB del volumen work. Escribe SI para confirmar: " r; \
	[ "$$r" = "SI" ] && docker compose down -v || echo "cancelado"
