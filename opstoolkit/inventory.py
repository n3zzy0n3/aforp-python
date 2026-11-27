"""Inventaire du parc : CSV (lab 2.2) et YAML (lab 2.3)."""
import csv
import logging
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

THRESHOLD = 90
REQUIRED_KEYS = {"name", "host", "role", "ports"}



# Analyse du parc (jour 1, lab 1.2)
def count_by_role(servers): 
    counts = {}
    for s in servers:
        counts[s["role"]] = counts.get(s["role"], 0) + 1
    return counts


def down_servers(servers):
	counts = []
	for s in servers:
		if not s["up"]:
			counts.append(s["name"]) 
	return counts


def overloaded(servers, threshold=90): 
	counts = []
	for s in servers:
		if s["cpu"] > threshold:
			counts.append(s["name"])
	return counts

# path accepte un texte ou un Path ; la fonction renvoie la liste des serveurs valides
def read_servers_csv(path: str | Path) -> list[dict]:
    """Lit un CSV de serveurs ; les lignes invalides sont ignorées et journalisées (lab 2.2).

    Colonnes attendues : name, ip, role, os, cpu, ram_gb, up. Dans un CSV, tout est texte :
    cpu et ram_gb sont convertis en entiers, up en booléen.

    Paramètres :
        path : chemin du fichier CSV, par exemple « data/servers.csv ».

    Renvoie :
        La liste des serveurs valides, un dictionnaire par serveur.

    Lève :
        FileNotFoundError : le fichier n'existe pas ; main() en fait un message clair.

    Résultat attendu : 50 serveurs pour data/servers.csv. Pour data/servers_piege.csv, trois
    avertissements : « Ligne 5 ignorée », « Ligne 10 ignorée » et « Ligne 15 ignorée ».
    """
    # Liste des serveurs valides
    servers = []
    # newline="" est exigé par le module csv ; UTF-8 pour les accents
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Parcours des lignes de données ; les lignes vides sont sautées automatiquement
        for row in reader:
            lineno = reader.line_num
            # Bloc surveillé : une ligne mal formée ne doit pas arrêter la lecture
            try:
                # Ajout du serveur, avec les conversions de type
                servers.append({
                    # Les champs texte sont recopiés tels quels
                    "name": row["name"], "ip": row["ip"], "role": row["role"], "os": row["os"],
                    "cpu": int(row["cpu"]), "ram_gb": int(row["ram_gb"]),
                    "up": row["up"].strip().lower() == "true",
                })
            # Colonne absente de l'en-tête (KeyError), champ manquant en fin de ligne (TypeError,
            # AttributeError) ou valeur non numérique (ValueError)
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                # La ligne est ignorée, mais le journal dit laquelle et pourquoi
                log.warning("Ligne %d ignorée : %r (%s)", lineno, row, exc)
    # Renvoi des serveurs valides
    return servers


# Reçoit la liste des serveurs ; renvoie un dictionnaire rôle → statistiques
def stats_by_role(servers: list[dict]) -> dict[str, dict]:
    """Calcule, pour chaque rôle, le nombre de serveurs, le CPU moyen et la RAM totale (lab 2.2).

    Paramètres :
        servers : liste des serveurs, avec les clés « role », « cpu » et « ram_gb ».

    Renvoie :
        Un dictionnaire trié par rôle : {rôle: {"count": n, "cpu_avg": moyenne arrondie à 0,1,
        "ram_gb": total}}.

    Exemple :
        >>> servers = [{"role": "web", "cpu": 40, "ram_gb": 16},
        ...            {"role": "web", "cpu": 51, "ram_gb": 32},
        ...            {"role": "db", "cpu": 70, "ram_gb": 64}]
        >>> list(stats_by_role(servers))
        ['db', 'web']
        >>> stats_by_role(servers)["web"]
        {'count': 2, 'cpu_avg': 45.5, 'ram_gb': 48}
    """
    # Totaux intermédiaires, par rôle
    stats: dict[str, dict] = {}
    # Parcours de chaque serveur
    for s in servers:
        # Totaux du rôle de ce serveur ; setdefault les crée à zéro au premier serveur du rôle
        st = stats.setdefault(s["role"], {"count": 0, "cpu_total": 0, "ram_gb": 0})
        st["count"] += 1
        st["cpu_total"] += s["cpu"]
        st["ram_gb"] += s["ram_gb"]
    # Résultat final, rôle par rôle
    result = {}
    # sorted trie les couples (rôle, totaux) par ordre alphabétique des rôles
    for role, st in sorted(stats.items()):
        cpu_avg = round(st["cpu_total"] / st["count"], 1)
        # Seules les valeurs utiles sont conservées : le total des CPU disparaît
        result[role] = {"count": st["count"], "cpu_avg": cpu_avg, "ram_gb": st["ram_gb"]}
    # Renvoi des statistiques
    return result


# Exception métier : elle hérite d'Exception, comme InventaireInvalide au jour 1
class InventoryError(Exception):
    """Inventaire YAML absent, mal formé ou incomplet, ou environnement inconnu (lab 2.3).

    main() l'attrape pour afficher un message clair et renvoyer le code 2.
    """


# path accepte un texte ou un Path ; la fonction renvoie le contenu du YAML sous forme de dictionnaire
def load_inventory(path: str | Path) -> dict:
    """Charge l'inventaire YAML et vérifie sa structure (lab 2.3).

    Paramètres :
        path : chemin du fichier YAML ; la ligne de commande passe « data/inventory.yaml » par défaut.

    Renvoie :
        Le contenu du fichier : {"environments": {nom: {"servers": [serveur, …]}, …}}.

    Lève :
        InventoryError : fichier introuvable, YAML invalide (une tabulation suffit), clé
        « environments » absente, environnement vide, ou serveur sans name, host, role ou ports.
        Exemple de message : « prod, serveur n°2 : champs manquants ['ports'] ».
    """
    # Bloc surveillé : les erreurs de lecture deviennent des InventoryError
    try:
        # Ouverture en lecture, en UTF-8
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    # Le fichier n'existe pas
    except FileNotFoundError as exc:
        # Message clair ; « from exc » conserve l'erreur d'origine
        raise InventoryError(f"Inventaire introuvable : {path}") from exc
    # Le fichier n'est pas du YAML valide, par exemple à cause d'une tabulation
    except yaml.YAMLError as exc:
        # Le message de PyYAML indique la ligne et la colonne fautives
        raise InventoryError(f"YAML invalide : {exc}") from exc
    # Le contenu doit être un dictionnaire, avec une clé « environments » qui est elle aussi un dictionnaire
    if not isinstance(data, dict) or not isinstance(data.get("environments"), dict):
        # Sinon, l'inventaire est inutilisable
        raise InventoryError("Clé 'environments' absente ou vide")
    # Parcours des environnements : env est le nom (dev, recette, prod), content son contenu
    for env, content in data["environments"].items():
        # Un environnement écrit « prod: » sans rien dessous vaut None : il est refusé
        if not isinstance(content, dict):
            # Message qui désigne l'environnement fautif
            raise InventoryError(f"Environnement {env} vide ou mal formé")
        # Serveurs numérotés à partir de 1 ; « or [] » couvre une clé servers absente ou vide
        for i, server in enumerate(content.get("servers") or [], start=1):
            missing = REQUIRED_KEYS - server.keys()
            # Un ensemble non vide est « vrai » : au moins un champ manque
            if missing:
                # sorted donne un message stable, par exemple ['host', 'ports']
                raise InventoryError(f"{env}, serveur n°{i} : champs manquants {sorted(missing)}")
    # L'inventaire est valide
    return data


# env vaut None par défaut : tous les environnements ; « str | None » signifie « texte, ou None »
def servers_of(inventory: dict, env: str | None = None) -> list[dict]:
    """Renvoie la liste à plat des serveurs, éventuellement filtrée par environnement (lab 2.3).

    Chaque serveur renvoyé est une copie qui porte en plus la clé « env » ; l'inventaire
    lui-même n'est pas modifié.

    Paramètres :
        inventory : inventaire chargé par load_inventory().
        env : nom d'un environnement (dev, recette, prod), ou None pour tous.

    Renvoie :
        La liste des serveurs, chacun avec la clé « env » en plus.

    Lève :
        InventoryError : l'environnement demandé n'existe pas.

    Exemple :
        >>> inv = {"environments": {"dev": {"servers": [{"name": "web-dev"}]},
        ...                         "prod": {"servers": [{"name": "db-prod"}]}}}
        >>> servers_of(inv, "prod")
        [{'name': 'db-prod', 'env': 'prod'}]
        >>> len(servers_of(inv))
        2
        >>> try:
        ...     servers_of(inv, "staging")
        ... except InventoryError as exc:
        ...     print(exc)
        Environnement inconnu : staging (disponibles : dev, prod)
    """
    # Raccourci vers le dictionnaire des environnements
    envs = inventory["environments"]
    if env is not None and env not in envs:
        # join liste les environnements disponibles, séparés par des virgules
        raise InventoryError(f"Environnement inconnu : {env} (disponibles : {', '.join(envs)})")
    selected = [env] if env else list(envs)
    # Liste à plat des serveurs
    result = []
    # Parcours des environnements retenus
    for e in selected:
        # Parcours de leurs serveurs ; « or [] » couvre une clé servers absente ou vide
        for s in envs[e].get("servers") or []:
            result.append({**s, "env": e})
    # Renvoi de la liste
    return result
