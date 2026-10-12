"""Donde vive el grafo en Fuseki. Para otra instalacion basta con cambiar FUSEKI_URL."""
import os

DATASET = "musica"
FUSEKI = os.environ.get("FUSEKI_URL", "http://localhost:3030")
QUERY = f"{FUSEKI}/{DATASET}/query"    # SPARQL de consulta
UPDATE = f"{FUSEKI}/{DATASET}/update"  # SPARQL de actualizacion
DATA = f"{FUSEKI}/{DATASET}/data"      # Graph Store Protocol, para subir los .ttl
ADMIN = os.environ.get("FUSEKI_ADMIN", "admin:admin")  # usuario:clave para crear el dataset
