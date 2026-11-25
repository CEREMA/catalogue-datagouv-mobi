RUN = uv run python -m catalogue_mobi.main
DUMP = catalogue_mobi.dump
CONTAINER = catalogue_mobi_postgres

help: ## Liste les commandes
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Installe les dépendances, y compris sentence-transformers
	uv sync --all-extras

lint: ## Vérifie le code
	uv run flake8 --max-line-length 100 catalogue_mobi tests

format: ## Formate le code
	uv run black catalogue_mobi tests

test: ## Tests unitaires (ni base, ni modèle, ni réseau)
	uv run pytest tests

db-up: ## Démarre PostgreSQL + pgvector (docker)
	docker compose up -d --wait

db-down: ## Arrête le conteneur PostgreSQL
	docker compose down

dump-db: ## Sauvegarde la base dans $(DUMP)
	docker exec $(CONTAINER) sh -c 'PGPASSWORD="$$POSTGRES_PASSWORD" pg_dump -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -F c -f /tmp/$(DUMP)'
	docker cp $(CONTAINER):/tmp/$(DUMP) ./$(DUMP)

restore-db: ## Recharge $(DUMP) dans la base (écrase les données)
	docker cp ./$(DUMP) $(CONTAINER):/tmp/$(DUMP)
	docker exec $(CONTAINER) sh -c 'PGPASSWORD="$$POSTGRES_PASSWORD" pg_restore -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" --clean --if-exists /tmp/$(DUMP)'

fetch: ## Télécharge les derniers exports du catalogue data.gouv.fr
	$(RUN) fetch

embed: ## Charge le catalogue, calcule les embeddings manquants (reprise possible)
	$(RUN) embed

embed-ontology: ## Réembedde la seule ontologie (à utiliser sans GPU)
	$(RUN) embed --ontology-only

attach: ## Rattachements par mots-clés (baseline), par règles et par embeddings (k plus proches)
	$(RUN) attach

enrich: ## Catégorie juridique des producteurs (API SIRENE, en cache)
	$(RUN) enrich

export: ## Écrit les tables à importer dans Grist (data/grist/)
	$(RUN) export

short-export: ## Idem, allégé pour l'import manuel dans Grist (taille, mémoire)
	$(RUN) export --short

update: ## Chaîne complète : fetch, embed, attach, enrich, export (cron)
	$(RUN) update

reset-db: ## Supprime les tables (puis relancer `make update`)
	$(RUN) reset-db
