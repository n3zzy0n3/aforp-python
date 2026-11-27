"""API FastAPI d'OpsToolkit : /health, /inventory et /checks (lab 4.2, bonus)."""
import os
from pathlib import Path


# Fabrique de l'application : python lab4.py serve l'appelle, puis la confie à uvicorn
def create_app(inventory_path: str | Path | None = None):
    """Construit l'API d'OpsToolkit : /health, /inventory et /checks (lab 4.2).

    Paramètres :
        inventory_path : fichier d'inventaire ; None (défaut) pour OPS_INVENTORY, ou data/inventory.yaml.

    Renvoie :
        L'application FastAPI. Sa documentation interactive est servie sur /docs.

    Résultats attendus avec le labo (python lab4.py serve, puis curl) :
        /health donne {"status":"ok"} ; /inventory?env=dev la liste des serveurs de dev ;
        /checks?env=dev {"ok":true,"results":[…]} ; /inventory?env=nope une erreur 404 avec son détail.
    """
    # Import ici : FastAPI n'est installé qu'au lab 4.2
    from fastapi import FastAPI, HTTPException

    # Fonctions du package, importées ici comme fastapi
    from .health import check_targets
    from .inventory import InventoryError, load_inventory, servers_of

    # Chemin de l'inventaire : paramètre, sinon variable d'environnement, sinon valeur par défaut
    path = inventory_path or os.environ.get("OPS_INVENTORY", "data/inventory.yaml")
    # L'application ; title et version apparaissent dans /docs
    app = FastAPI(title="OpsToolkit API", version="1.0")

    @app.get("/health")
    def health():
        """Santé de l'API elle-même."""
        # FastAPI convertit le dictionnaire en JSON
        return {"status": "ok"}

    # env est un paramètre de requête facultatif : /inventory?env=dev
    @app.get("/inventory")
    def inventory(env: str | None = None):
        """Serveurs d'un environnement, ou de tous."""
        # Bloc surveillé : un environnement inconnu ne doit pas donner une erreur 500
        try:
            # Même fonction que la sous-commande inventory du jour 2
            return servers_of(load_inventory(path), env)
        # Environnement inconnu ou inventaire invalide
        except InventoryError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Même paramètre env que /inventory
    @app.get("/checks")
    def checks(env: str | None = None):
        """Test des ports de l'environnement, avec un booléen global."""
        # Bloc surveillé : même traitement de l'environnement inconnu que dans inventory()
        try:
            results: list[dict] = check_targets(servers_of(load_inventory(path), env))
        # Environnement inconnu : 404
        except InventoryError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"ok": all(r["ok"] for r in results), "results": results}

    # Application prête
    return app
