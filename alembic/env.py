import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv
from alembic import context
from sqlalchemy import create_engine, pool
from app.database import Base
from app.config import settings 

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# Importation des modèles
from app.database import Base
from app.models import (
    model_user, model_role, model_client, model_produit, model_categorie, 
    model_fournisseur, model_commande, model_intervention, model_historique_intervention, 
    model_historique_general, model_facture, model_paiement, model_depense, model_rapport, 
    model_unite_produit, model_notification, model_reset_token, model_galerie, model_client_produit,
    model_tutoriel,model_clientfollowup, model_depot, model_depot_service, model_depot_tarif, model_facture_depot,
    model_depot_tarif_items, model_souscription
)

# Config Alembic
config = context.config
fileConfig(config.config_file_name)

# ⛓ Injecte l'URL de la DB depuis settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline():
    """Migration en mode offline."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Migration en mode online."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()