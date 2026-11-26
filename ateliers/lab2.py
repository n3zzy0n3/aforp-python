"""Labs du jour 2 — Fichiers, données et logs : code à trous.

Ce fichier contient toutes les fonctions des labs 2.1 à 2.5 et une ligne de commande pour les lancer.
L'essentiel est écrit : vous fermez les trous, dans l'ordre de leurs numéros.

Reconnaître un trou
    Chaque trou est annoncé par un commentaire « TODO n », suivi d'une « Aide ». La ligne à remplacer
    se termine par le repère « # <- TODO n ». Elle contient une valeur provisoire (False, 0, [], pass…)
    qui laisse le fichier tourner, mais donne un résultat faux ou vide. Remplacez toute cette ligne
    par le bon code, en gardant son indentation, et supprimez le repère.

Installation, dans ~/aforp-python, venv activé
    cp -r ~/lab/data/app-logs ~/lab/data/access.log ~/lab/data/inventory.yaml data/
    cp ~/lab/data/servers.csv ~/lab/data/servers_piege.csv data/
    Puis copier lab2.py à la racine du projet, à côté du dossier data/.

Lab  Trous          Commandes de contrôle
2.1  TODO 1 à 6     python lab2.py scan data/app-logs                    (Total erreurs : 61)
                    python lab2.py scan absent; echo "code=$?"             (code=2)
2.2  TODO 7 à 14    python lab2.py stats data/servers.csv --out-dir resultats
                    python lab2.py stats data/servers_piege.csv --out-dir resultats-piege
2.3  TODO 15 à 20   python lab2.py inventory --env prod
                    python lab2.py inventory --env staging; echo "code=$?" (code=2)
2.4  TODO 21 à 27   python lab2.py logs data/access.log -o rapport-logs.json
2.5  TODO 28 à 30   python lab2.py report --env dev --format html -o rapport.html

Vérifier les fonctions avec les exemples des docstrings
    python -m doctest lab2.py
    Aucun affichage : tous les exemples passent. Sinon, doctest montre l'exemple en échec,
    le résultat attendu et le résultat obtenu.

Codes retour : 0 = tout va bien, 2 = erreur d'usage ou de configuration (convention d'OpsToolkit).
"""
# argparse : lecture des sous-commandes et des options de la ligne de commande
import argparse
# csv : lecture et écriture de fichiers CSV (lab 2.2)
import csv
# json : écriture de fichiers JSON (labs 2.2 et 2.4)
import json
# logging : messages de suivi avec un niveau, distincts du résultat affiché par print
import logging
# re : expressions régulières, pour découper les lignes de log Nginx (lab 2.4)
import re
# sys : sys.exit transmet le code retour au shell
import sys
# Counter : dictionnaire spécialisé dans le comptage, avec la méthode most_common() (lab 2.4)
from collections import Counter
# datetime : date et heure de génération du rapport (lab 2.5)
from datetime import datetime
# Path : chemins de fichiers sous forme d'objets, avec l'opérateur / pour les assembler (lab 2.1)
from pathlib import Path

# yaml, fourni par le paquet PyYAML : lecture de l'inventaire (lab 2.3)
import yaml
# Environment : moteur de gabarits Jinja2, pour les rapports (lab 2.5)
from jinja2 import Environment

# Journal propre à ce fichier ; main() règle son niveau et son format
log = logging.getLogger("lab2")
# Champs obligatoires de chaque serveur de l'inventaire YAML ; un ensemble, pour calculer une différence
REQUIRED_KEYS = {"name", "host", "role", "ports"}


# ======================================================================================================
# Lab 2.1 — Fichiers texte et pathlib
# ======================================================================================================

# folder est un Path ; la fonction renvoie une liste de dictionnaires, un par fichier .log
def scan_logs(folder: Path) -> list[dict]:
    """Analyse les journaux d'un dossier : taille et nombre de lignes par niveau (lab 2.1).

    Seuls les fichiers .log sont retenus, sous-dossiers compris : notes.txt est donc ignoré.
    Une ligne compte pour un seul niveau, le premier trouvé.

    Paramètres :
        folder : dossier à analyser, par exemple Path("data/app-logs").

    Renvoie :
        Une liste triée par chemin. Chaque élément est un dictionnaire {"file": chemin relatif
        au dossier, "size_kb": taille en Ko arrondie à 0,1, "INFO": n, "WARNING": n, "ERROR": n}.

    Résultat attendu sur data/app-logs :
        api-commandes.log 20.1 Ko, 299 INFO, 71 WARNING, 30 ERROR ;
        archives/api-commandes.2026-11-15.log 0.2 Ko, 0, 0, 3 ;
        batch-nuit.log 5.6 Ko, 92, 18, 10 ; paiements.log 11.5 Ko, 179, 53, 18.
    """
    # Liste des résultats, remplie fichier par fichier
    results = []
    # TODO 1 : parcourir les fichiers .log du dossier ET de ses sous-dossiers, triés par nom.
    # Aide : folder.rglob("*.log") trouve les fichiers à toutes les profondeurs ; sorted(...) les trie.
    for path in sorted(folder.rglob("*.log")):
        # Compteurs de ce fichier, remis à zéro pour chaque fichier
        levels = {"INFO": 0, "WARNING": 0, "ERROR": 0}
        # Ouverture en UTF-8 ; errors="replace" remplace un octet illisible au lieu de planter
        with path.open(encoding="utf-8", errors="replace") as f:
            # Lecture ligne à ligne : la mémoire reste faible, même pour un log de 2 Go
            for line in f:
                # On essaie chaque niveau, dans l'ordre INFO, WARNING, ERROR
                for level in levels:
                    # TODO 2 : condition vraie si le niveau apparaît dans la ligne, entouré d'espaces.
                    # Aide : f" {level} " in line   (les espaces évitent de compter « INFORMATION »)
                    if f" {level} " in line:
                        # Le niveau est trouvé : on l'ajoute au compteur
                        levels[level] += 1
                        # Une ligne n'a qu'un niveau : inutile de tester les suivants
                        break
        # TODO 3 : taille du fichier en Ko, arrondie à 1 décimale.
        # Aide : path.stat().st_size donne la taille en octets ; 1 Ko = 1024 octets ; round(x, 1).
        size_kb = round(path.stat().st_size / 1024, 1)
        # Ajout du résultat de ce fichier
        results.append({
            # TODO 4 : chemin RELATIF au dossier analysé, pour afficher « archives/… ».
            # Aide : path.relative_to(folder).as_posix()   (as_posix écrit des / même sous Windows)
            "file": path.relative_to(folder).as_posix(),
            # Taille calculée au TODO 3
            "size_kb": size_kb,
            # ** recopie les trois compteurs INFO, WARNING et ERROR dans ce dictionnaire
            **levels,
        })
    # Renvoi de la liste complète
    return results


# ======================================================================================================
# Lab 2.2 — CSV et JSON : statistiques du parc
# ======================================================================================================

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
        # TODO 7 : créer un lecteur qui renvoie chaque ligne sous forme de dictionnaire.
        # Aide : csv.DictReader(f) prend la 1re ligne comme en-têtes : row["name"], row["cpu"]…
        reader = csv.DictReader(f)
        # Parcours des lignes de données ; les lignes vides sont sautées automatiquement
        for row in reader:
            # TODO 8 : numéro réel de la ligne dans le fichier, lignes vides comprises.
            # Aide : reader.line_num   (un compteur enumerate se décale dès la première ligne vide)
            lineno = reader.line_num
            # Bloc surveillé : une ligne mal formée ne doit pas arrêter la lecture
            try:
                # Ajout du serveur, avec les conversions de type
                servers.append({
                    # Les champs texte sont recopiés tels quels
                    "name": row["name"], "ip": row["ip"], "role": row["role"], "os": row["os"],
                    # TODO 9 : convertir cpu et ram_gb en entiers ; « N/A » ou "" lèvent ValueError.
                    # Aide : int(row["cpu"]) et int(row["ram_gb"])
                    "cpu": int(row["cpu"]), "ram_gb": int(row["ram_gb"]),
                    # TODO 10 : True seulement si la colonne up contient « true », quelle que soit la casse.
                    # Aide : row["up"].strip().lower() == "true"   (attention : bool("false") vaut True)
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
        # TODO 11 : ajouter ce serveur aux totaux de son rôle : 1 serveur, son CPU, sa RAM.
        # Aide : st["count"] += 1, puis la même chose pour st["cpu_total"] et st["ram_gb"] (3 lignes).
        st["count"] += 1
        st["cpu_total"] += s["cpu"]
        st["ram_gb"] += s["ram_gb"]
    # Résultat final, rôle par rôle
    result = {}
    # sorted trie les couples (rôle, totaux) par ordre alphabétique des rôles
    for role, st in sorted(stats.items()):
        # TODO 12 : CPU moyen = total des CPU / nombre de serveurs, arrondi à 1 décimale.
        # Aide : round(st["cpu_total"] / st["count"], 1)
        cpu_avg = round(st["cpu_total"] / st["count"], 1)
        # Seules les valeurs utiles sont conservées : le total des CPU disparaît
        result[role] = {"count": st["count"], "cpu_avg": cpu_avg, "ram_gb": st["ram_gb"]}
    # Renvoi des statistiques
    return result


# Reçoit les statistiques et le dossier de sortie ; écrit deux fichiers et ne renvoie rien
def write_stats(stats: dict, out_dir: Path) -> None:
    """Écrit les statistiques dans out_dir/stats.json et out_dir/stats.csv (lab 2.2).

    Paramètres :
        stats : statistiques produites par stats_by_role().
        out_dir : dossier de sortie, créé s'il n'existe pas.
    """
    # Création du dossier et de ses parents ; exist_ok évite une erreur s'il existe déjà
    out_dir.mkdir(parents=True, exist_ok=True)
    # TODO 13 : texte JSON des statistiques, indenté de 2 espaces, accents conservés.
    # Aide : json.dumps(stats, indent=2, ensure_ascii=False)
    text = json.dumps(stats, indent=2, ensure_ascii=False)
    # Écriture du JSON ; l'opérateur / assemble le dossier et le nom du fichier
    (out_dir / "stats.json").write_text(text, encoding="utf-8")
    # Ouverture du CSV en écriture ; newline="" évite des lignes vides en trop sous Windows
    with open(out_dir / "stats.csv", "w", newline="", encoding="utf-8") as f:
        # Écrivain CSV : il place les virgules et les guillemets à notre place
        writer = csv.writer(f)
        # Ligne d'en-tête
        writer.writerow(["role", "count", "cpu_avg", "ram_gb"])
        # Une ligne par rôle
        for role, s in stats.items():
            # TODO 14 : écrire la ligne du rôle, dans l'ordre des colonnes de l'en-tête.
            # Aide : writer.writerow([role, s["count"], s["cpu_avg"], s["ram_gb"]])
            writer.writerow([role, s["count"], s["cpu_avg"], s["ram_gb"]])


# ======================================================================================================
# Lab 2.3 — YAML : inventaire multi-environnements
# ======================================================================================================

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
            # TODO 15 : charger le YAML en objets Python, SANS jamais utiliser yaml.load.
            # Aide : yaml.safe_load(f)   (yaml.load peut créer des objets Python arbitraires)
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
            # TODO 16 : champs obligatoires absents de ce serveur, sous forme d'ensemble.
            # Aide : REQUIRED_KEYS - server.keys()   (différence de deux ensembles)
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
    # TODO 17 : condition vraie si un environnement est demandé ET absent de l'inventaire.
    # Aide : env is not None and env not in envs
    if env is not None and env not in envs:
        # join liste les environnements disponibles, séparés par des virgules
        raise InventoryError(f"Environnement inconnu : {env} (disponibles : {', '.join(envs)})")
    # TODO 18 : environnements à parcourir : [env] si un environnement est demandé, sinon tous.
    # Aide : [env] if env else list(envs)
    selected = [env] if env else list(envs)
    # Liste à plat des serveurs
    result = []
    # Parcours des environnements retenus
    for e in selected:
        # Parcours de leurs serveurs ; « or [] » couvre une clé servers absente ou vide
        for s in envs[e].get("servers") or []:
            # TODO 19 : ajouter à result une COPIE du serveur s, avec la clé "env" en plus.
            # Aide : result.append({**s, "env": e})   (** recopie toutes les clés de s)
            result.append({**s, "env": e})
    # Renvoi de la liste
    return result


# ======================================================================================================
# Lab 2.4 — Analyseur de logs Nginx
# ======================================================================================================

# Motif d'une ligne Nginx au format « combined » ; (?P<nom>…) est un groupe nommé, lu avec m["nom"]
# TODO 21 : compléter les deux derniers groupes : statut (3 chiffres) et taille (chiffres, ou « - »).
# Aide : \d{3} et \d+|-   (construire le motif sur regex101.com avec 3 vraies lignes du log)
PATTERN = re.compile(
    # IP, deux champs ignorés, date entre crochets, puis méthode et URL de la requête entre guillemets
    r'(?P<ip>\S+) \S+ \S+ \[(?P<date>[^\]]+)\] "(?P<method>[A-Z]+) (?P<url>\S+) [^"]*" '
    # Statut HTTP et taille de la réponse
    r"(?P<status>\d{3}) (?P<size>\d+|-)"
)


# Renvoie un dictionnaire de champs, ou None : « dict | None » signifie « dictionnaire, ou None »
def parse_line(line: str) -> dict | None:
    """Découpe une ligne de log Nginx en champs (lab 2.4).

    Paramètres :
        line : une ligne du fichier access.log.

    Renvoie :
        Un dictionnaire {"ip", "date", "method", "url", "status", "size"}, avec status et size
        en entiers, ou None si la ligne ne suit pas le format attendu.

    Exemple :
        >>> line = ('203.0.113.66 - - [16/Nov/2026:00:00:17 +0100] '
        ...         '"GET /recherche HTTP/1.1" 502 120 "-" "curl/8.5"')
        >>> e = parse_line(line)
        >>> e["ip"], e["url"], e["status"], e["size"]
        ('203.0.113.66', '/recherche', 502, 120)
        >>> parse_line("### rotation du fichier ###") is None
        True
    """
    # TODO 22 : appliquer le motif à partir du DÉBUT de la ligne.
    # Aide : PATTERN.match(line)   (match part du début ; search chercherait n'importe où)
    match = PATTERN.match(line)
    # Pas de correspondance : la ligne est corrompue ou n'est pas une requête
    if match is None:
        # None signale à l'appelant une ligne à ignorer
        return None
    # Dictionnaire {nom du groupe: texte capturé}
    entry = match.groupdict()
    # TODO 23 : le statut capturé est du texte (« 502 ») : le convertir en entier.
    # Aide : int(entry["status"])
    entry["status"] = int(entry["status"])
    # Taille en entier ; Nginx écrit « - » quand la réponse n'a pas de corps
    entry["size"] = 0 if entry["size"] == "-" else int(entry["size"])
    # Renvoi des champs de la ligne
    return entry


# top vaut 5 par défaut ; la fonction renvoie un dictionnaire prêt à écrire en JSON
def analyze(path: str | Path, top: int = 5) -> dict:
    """Analyse un fichier de log Nginx et renvoie un rapport sérialisable en JSON (lab 2.4).

    Paramètres :
        path : chemin du fichier de log, par exemple « data/access.log ».
        top : nombre d'éléments de chaque classement (option --top, 5 par défaut).

    Renvoie :
        Un dictionnaire {"file", "total_requests", "invalid_lines", "top_ips", "status_families",
        "top_5xx_urls"}. Les classements sont des listes de couples (valeur, nombre), du plus
        fréquent au moins fréquent.

    Lève :
        FileNotFoundError : le fichier n'existe pas ; main() en fait un message clair.

    Résultat attendu sur data/access.log : 5000 requêtes et 3 lignes ignorées ; top IP 203.0.113.66
    (1130), 198.51.100.23 (766), 192.168.1.19 (124), 192.168.1.13 (118), 192.168.1.15 (116) ;
    familles 2xx 4080, 3xx 117, 4xx 541, 5xx 262 ; URL en 5xx : /recherche (142), /api/paiement (120).
    """
    # Deux compteurs simples, à zéro : requêtes valides et lignes ignorées
    total = invalid = 0
    # Trois compteurs : par adresse IP, par famille de statut, par URL en erreur 5xx
    ips, families, errors_5xx = Counter(), Counter(), Counter()
    # Lecture en UTF-8 ; errors="replace" remplace un octet illisible au lieu de planter
    with open(path, encoding="utf-8", errors="replace") as f:
        # Lecture ligne à ligne, sans charger tout le fichier en mémoire
        for line in f:
            # Découpage de la ligne en champs
            entry = parse_line(line)
            # Ligne non conforme : on la compte, sans planter
            if entry is None:
                # Une ligne ignorée de plus
                invalid += 1
                # continue passe directement à la ligne suivante
                continue
            # Une requête valide de plus
            total += 1
            # TODO 24 : compter une requête de plus pour l'adresse IP de cette ligne.
            # Aide : ips[entry["ip"]] += 1   (un Counter part de 0 pour une clé inconnue)
            ips[entry["ip"]] += 1
            # TODO 25 : compter la ligne dans sa famille de statut : 404 → "4xx", 502 → "5xx".
            # Aide : families[f"{entry['status'] // 100}xx"] += 1   (// est la division entière)
            families[f"{entry['status'] // 100}xx"] += 1
            # TODO 26 : condition vraie si le statut est une erreur serveur (500 ou plus).
            # Aide : entry["status"] >= 500
            if entry["status"] >= 500:
                # Une erreur 5xx de plus pour cette URL
                errors_5xx[entry["url"]] += 1
    # Rapport final : seulement des types que json sait écrire (texte, nombres, listes, dictionnaires)
    return {
        # Chemin du fichier analysé, converti en texte
        "file": str(path),
        # Nombre de requêtes valides
        "total_requests": total,
        # Nombre de lignes ignorées
        "invalid_lines": invalid,
        # TODO 27 : les `top` adresses IP les plus fréquentes, puis les `top` URL en 5xx (ligne plus bas).
        # Aide : ips.most_common(top) et errors_5xx.most_common(top)
        "top_ips": ips.most_common(top),
        # Familles de statut triées par nom : 2xx, 3xx, 4xx, 5xx
        "status_families": dict(sorted(families.items())),
        # Classement des URL en erreur 5xx (second trou du TODO 27)
        "top_5xx_urls": errors_5xx.most_common(top),
    }


# ======================================================================================================
# Lab 2.5 — Rapports Markdown et HTML avec Jinja2
# ======================================================================================================

# Gabarit Markdown ; {{ … }} affiche une valeur, {% … %} est une instruction, {# … #} un commentaire
# TODO 28 : dans le gabarit, remplacer la ligne {# TODO 28 … #} par une boucle {% for %} … {% endfor %}
#           qui écrit une ligne de tableau par serveur, avec les ports séparés par des virgules.
# Aide : diapo 32, ou la boucle du gabarit HTML juste en dessous ; filtre join(', ') pour les ports.
MARKDOWN = """# Rapport d'exploitation CloudNova — {{ generated }}

## Inventaire ({{ servers | length }} serveurs)

| Environnement | Serveur | Rôle | Hôte | Ports |
| --- | --- | --- | --- | --- |
{% for s in servers %}| {{ s.env }} | {{ s.name }} | {{ s.role }} | {{ s.host }} | {{ s.ports | join(', ') }} |
{% endfor %}
"""

# Gabarit HTML, complet : une page autonome avec son style et un tableau des serveurs
HTML = """<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Rapport CloudNova</title><style>
body{font-family:sans-serif;margin:2rem;color:#1b2a4a}h1{color:#1d3a6e}
table{border-collapse:collapse}td,th{border:1px solid #ccd;padding:.3rem .6rem}
th{background:#1d3a6e;color:#fff}</style></head><body>
<h1>Rapport d'exploitation CloudNova</h1><p>Généré le {{ generated }}</p>
<table><tr><th>Environnement</th><th>Serveur</th><th>Rôle</th><th>Hôte</th><th>Ports</th></tr>
{% for s in servers %}<tr><td>{{ s.env }}</td><td>{{ s.name }}</td><td>{{ s.role }}</td>
<td>{{ s.host }}</td><td>{{ s.ports | join(', ') }}</td></tr>{% endfor %}</table>
</body></html>"""


# fmt vaut "md" par défaut ; la fonction renvoie le texte du rapport
def render(servers: list[dict], fmt: str = "md") -> str:
    """Produit le rapport d'inventaire au format Markdown ou HTML (lab 2.5).

    Au jour 3, un paramètre health ajoutera l'état des services (option --with-health).

    Paramètres :
        servers : serveurs renvoyés par servers_of(), avec la clé « env ».
        fmt : « md » pour Markdown (défaut) ou « html ».

    Renvoie :
        Le texte du rapport.

    Exemple :
        >>> servers = [{"env": "prod", "name": "web-prod", "role": "web",
        ...             "host": "127.0.0.1", "ports": [8081]}]
        >>> "| prod | web-prod | web | 127.0.0.1 | 8081 |" in render(servers)
        True
        >>> pirate = [{**servers[0], "name": "<b>pirate</b>"}]
        >>> "&lt;b&gt;pirate&lt;/b&gt;" in render(pirate, fmt="html")
        True
    """
    # TODO 29 : activer l'échappement automatique en HTML seulement : un nom de serveur comme
    #           « <script> » doit s'afficher tel quel, et non s'exécuter dans le navigateur.
    # Aide : Environment(autoescape=fmt == "html")
    env = Environment(autoescape=fmt == "html")
    # TODO 30 : choisir le gabarit HTML si fmt vaut "html", sinon le gabarit Markdown.
    # Aide : env.from_string(HTML if fmt == "html" else MARKDOWN)
    template = env.from_string(HTML if fmt == "html" else MARKDOWN)
    # Remplissage du gabarit : servers et generated deviennent des variables du gabarit
    return template.render(servers=servers, generated=datetime.now().strftime("%d/%m/%Y %H:%M"))


# ======================================================================================================
# Ligne de commande : une sous-commande par lab (fournie, sauf les TODO 5, 6 et 20)
# ======================================================================================================

# args est l'objet rempli par argparse ; la fonction renvoie le code retour
def cmd_scan(args: argparse.Namespace) -> int:
    """Sous-commande « scan » : tableau des journaux d'un dossier (lab 2.1).

    Paramètres :
        args : arguments lus par argparse ; args.folder est le dossier à analyser.

    Renvoie :
        0 si l'analyse a eu lieu, 2 si le dossier n'existe pas.
    """
    # TODO 5 : condition vraie si args.folder n'est pas un dossier existant.
    # Aide : not args.folder.is_dir()
    if not args.folder.is_dir():
        # Message clair dans le journal, sans trace Python
        log.error("Dossier introuvable : %s", args.folder)
        # Code 2 : erreur d'usage
        return 2
    # Analyse du dossier
    rows = scan_logs(args.folder)
    # En-tête du tableau : :<38 aligne à gauche sur 38 caractères, :>6 à droite sur 6
    print(f"{'FICHIER':<38}{'Ko':>6}{'INFO':>6}{'WARN':>6}{'ERR':>5}")
    # Une ligne par fichier
    for r in rows:
        # Mêmes largeurs de colonnes que l'en-tête
        print(f"{r['file']:<38}{r['size_kb']:>6}{r['INFO']:>6}{r['WARNING']:>6}{r['ERROR']:>5}")
    # TODO 6 : total des erreurs de tous les fichiers.
    # Aide : sum(r["ERROR"] for r in rows)
    total = sum(r["ERROR"] for r in rows)
    # Ligne de total
    print(f"Total erreurs : {total}")
    # Code 0 : tout s'est bien passé
    return 0


# Même signature pour toutes les sous-commandes : les arguments en entrée, le code retour en sortie
def cmd_stats(args: argparse.Namespace) -> int:
    """Sous-commande « stats » : statistiques du parc par rôle (lab 2.2).

    Écrit stats.json et stats.csv dans args.out_dir, puis affiche une ligne par rôle.

    Paramètres :
        args : arguments lus par argparse ; args.csv est le fichier CSV, args.out_dir le dossier de sortie.

    Renvoie :
        0. Un fichier introuvable est traité par main(), qui renvoie 2.
    """
    # Lecture du CSV ; read_servers_csv journalise elle-même les lignes ignorées
    servers = read_servers_csv(args.csv)
    # Calcul des statistiques par rôle
    stats = stats_by_role(servers)
    # Écriture de stats.json et stats.csv
    write_stats(stats, args.out_dir)
    # Une ligne par rôle
    for role, s in stats.items():
        # Rôle, nombre de serveurs, CPU moyen et RAM totale, alignés en colonnes
        print(f"{role:<11}{s['count']:>3} serveurs  CPU moyen {s['cpu_avg']:>5} %  RAM {s['ram_gb']:>4} Go")
    # Code 0 : tout s'est bien passé
    return 0


# Même signature pour toutes les sous-commandes
def cmd_inventory(args: argparse.Namespace) -> int:
    """Sous-commande « inventory » : tableau des serveurs, filtrable par environnement (lab 2.3).

    Paramètres :
        args : arguments lus par argparse ; args.inventory est le fichier YAML, args.env
            l'environnement demandé (None pour tous).

    Renvoie :
        0. Une InventoryError est traitée par main(), qui renvoie 2.
    """
    # TODO 20 : charger l'inventaire args.inventory, puis ne garder que l'environnement args.env.
    # Aide : servers_of(load_inventory(args.inventory), args.env)
    servers = servers_of(load_inventory(args.inventory), args.env)
    # En-tête du tableau
    print(f"{'ENV':<9}{'NOM':<13}{'RÔLE':<9}{'HÔTE':<12}PORTS")
    # Une ligne par serveur
    for s in servers:
        # map(str, …) convertit chaque port en texte, pour que join puisse les assembler
        print(f"{s['env']:<9}{s['name']:<13}{s['role']:<9}{s['host']:<12}{','.join(map(str, s['ports']))}")
    # Code 0 : tout s'est bien passé
    return 0


# Même signature pour toutes les sous-commandes
def cmd_logs(args: argparse.Namespace) -> int:
    """Sous-commande « logs » : analyse d'un log Nginx, affichée et enregistrée en JSON (lab 2.4).

    Paramètres :
        args : arguments lus par argparse ; args.file est le log, args.top la taille des
            classements, args.output le fichier JSON à écrire (facultatif).

    Renvoie :
        0. Un fichier introuvable est traité par main(), qui renvoie 2.
    """
    # Analyse du fichier de log
    report = analyze(args.file, args.top)
    # Texte JSON indenté ; ensure_ascii=False garde les accents lisibles
    text = json.dumps(report, indent=2, ensure_ascii=False)
    # Affichage du rapport : c'est le résultat de la commande
    print(text)
    # Avec l'option -o, le rapport est aussi enregistré
    if args.output:
        # Écriture du fichier JSON
        Path(args.output).write_text(text, encoding="utf-8")
        # Confirmation dans le journal
        log.info("Rapport écrit dans %s", args.output)
    # Code 0 : tout s'est bien passé
    return 0


# Même signature pour toutes les sous-commandes
def cmd_report(args: argparse.Namespace) -> int:
    """Sous-commande « report » : rapport d'inventaire en Markdown ou en HTML (lab 2.5).

    Paramètres :
        args : arguments lus par argparse ; args.env, args.format (md ou html) et args.output.

    Renvoie :
        0. Une InventoryError est traitée par main(), qui renvoie 2.
    """
    # Serveurs de l'environnement demandé (fonctions des TODO 15 à 19)
    servers = servers_of(load_inventory(args.inventory), args.env)
    # Texte du rapport au format demandé
    content = render(servers, args.format)
    # Écriture du rapport en UTF-8
    Path(args.output).write_text(content, encoding="utf-8")
    # Confirmation pour l'utilisateur
    print(f"Rapport écrit dans {args.output}")
    # Code 0 : tout s'est bien passé
    return 0


# Renvoie l'analyseur de la ligne de commande, prêt à l'emploi
def build_parser() -> argparse.ArgumentParser:
    """Construit l'analyseur de la ligne de commande : options générales et sous-commandes.

    Chaque sous-commande enregistre, avec set_defaults(func=…), la fonction qui la traite.

    Renvoie :
        L'analyseur argparse.
    """
    # Analyseur principal ; prog fixe le nom affiché dans l'aide
    parser = argparse.ArgumentParser(prog="lab2", description="Labs du jour 2 : fichiers, données et logs")
    # Option générale : messages de niveau DEBUG
    parser.add_argument("-v", "--verbose", action="store_true", help="logs détaillés (DEBUG)")
    # Option générale : chemin de l'inventaire YAML, utilisé par inventory et report
    parser.add_argument("-i", "--inventory", default="data/inventory.yaml", help="fichier d'inventaire YAML")
    # Groupe des sous-commandes ; required=True oblige à en choisir une
    sub = parser.add_subparsers(dest="command", required=True)

    # Lab 2.1 : « scan DOSSIER » ; type=Path convertit directement le texte en Path
    p = sub.add_parser("scan", help="tableau des journaux d'un dossier (lab 2.1)")
    # Argument obligatoire : le dossier à analyser
    p.add_argument("folder", type=Path, help="dossier à analyser, par exemple data/app-logs")
    # Fonction appelée par main() pour cette sous-commande
    p.set_defaults(func=cmd_scan)

    # Lab 2.2 : « stats FICHIER.csv [--out-dir DOSSIER] »
    p = sub.add_parser("stats", help="statistiques du parc par rôle (lab 2.2)")
    # Argument obligatoire : le fichier CSV
    p.add_argument("csv", type=Path, help="fichier CSV des serveurs")
    # Dossier de sortie, « resultats » par défaut
    p.add_argument("--out-dir", type=Path, default=Path("resultats"), help="dossier de sortie")
    # Fonction appelée par main() pour cette sous-commande
    p.set_defaults(func=cmd_stats)

    # Lab 2.3 : « inventory [--env ENV] »
    p = sub.add_parser("inventory", help="afficher l'inventaire (lab 2.3)")
    # Environnement à afficher ; sans l'option, tous les environnements
    p.add_argument("--env", help="dev, recette ou prod (défaut : tous)")
    # Fonction appelée par main() pour cette sous-commande
    p.set_defaults(func=cmd_inventory)

    # Lab 2.4 : « logs FICHIER [--top N] [-o RAPPORT.json] »
    p = sub.add_parser("logs", help="analyser un log Nginx (lab 2.4)")
    # Argument obligatoire : le fichier de log
    p.add_argument("file", help="fichier de log Nginx")
    # Taille des classements, convertie en entier
    p.add_argument("--top", type=int, default=5, help="taille des classements (défaut : 5)")
    # Fichier JSON à écrire ; sans l'option, le rapport est seulement affiché
    p.add_argument("-o", "--output", help="écrire le rapport JSON dans ce fichier")
    # Fonction appelée par main() pour cette sous-commande
    p.set_defaults(func=cmd_logs)

    # Lab 2.5 : « report [--env ENV] [--format md|html] [-o FICHIER] »
    p = sub.add_parser("report", help="rapport Markdown ou HTML (lab 2.5)")
    # Environnement du rapport ; sans l'option, tous les environnements
    p.add_argument("--env", help="dev, recette ou prod (défaut : tous)")
    # Format du rapport ; choices refuse toute autre valeur
    p.add_argument("--format", choices=["md", "html"], default="md", help="format (défaut : md)")
    # Fichier à écrire
    p.add_argument("-o", "--output", default="rapport.md", help="fichier du rapport (défaut : rapport.md)")
    # Fonction appelée par main() pour cette sous-commande
    p.set_defaults(func=cmd_report)

    # Renvoi de l'analyseur complet
    return parser


# argv vaut None par défaut : argparse lit alors la vraie ligne de commande
def main(argv: list[str] | None = None) -> int:
    """Point d'entrée : lit la ligne de commande, lance la sous-commande, gère les erreurs prévues.

    Paramètres :
        argv : arguments de la ligne de commande ; None (défaut) lit sys.argv. Un test peut
            passer une liste, par exemple ["inventory", "--env", "prod"].

    Renvoie :
        Le code retour de la sous-commande, ou 2 pour une erreur d'inventaire ou un fichier introuvable.
    """
    # Lecture des arguments ; une option inconnue affiche l'usage et quitte avec le code 2
    args = build_parser().parse_args(argv)
    # Niveau DEBUG avec -v, INFO sinon ; format « NIVEAU message »
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")
    # Exécution surveillée : les erreurs prévues deviennent un message clair et le code 2
    try:
        # Appel de la fonction enregistrée par la sous-commande choisie
        return args.func(args)
    # Inventaire invalide ou environnement inconnu (lab 2.3)
    except InventoryError as exc:
        # Message clair, sans trace Python
        log.error("%s", exc)
        # Code 2 : erreur de configuration
        return 2
    # Fichier CSV ou log introuvable (labs 2.2 et 2.4)
    except FileNotFoundError as exc:
        # exc.filename contient le chemin demandé
        log.error("Fichier introuvable : %s", exc.filename)
        # Code 2 : erreur d'usage
        return 2


# Condition vraie seulement quand le fichier est lancé directement, pas quand il est importé
if __name__ == "__main__":
    # Lance main() et transmet son code retour au shell, visible avec « echo $? »
    sys.exit(main())

