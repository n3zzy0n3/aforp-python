"""Labs du jour 4 — API, conteneurs et cloud : code à trous.

Ce fichier contient toutes les fonctions des labs 4.1 à 4.5 et une ligne de commande pour les lancer.
L'essentiel est écrit : vous fermez les trous, dans l'ordre de leurs numéros.

Reconnaître un trou
    Chaque trou est annoncé par un commentaire « TODO n » qui décrit ce qu'il faut obtenir, suivi d'une
    « Aide » qui dit où chercher, sans donner la réponse. La ligne à remplacer se termine par le repère
    « # <- TODO n ». Elle contient une valeur provisoire (False, 0, [], pass…) qui laisse le fichier
    tourner, mais donne un résultat faux ou vide. Remplacez toute cette ligne par votre code (une ou
    plusieurs lignes), en gardant son indentation, et supprimez le repère.

Où chercher
    Les diapositives 51 à 59 du cours : une par notion ou par lab. La documentation officielle de chaque
    bibliothèque complète : requests, FastAPI, Docker SDK for Python, boto3, prometheus_client.

Règles du jour, vérifiées au livrable n°3
    Un timeout sur chaque appel réseau ; le code HTTP lu avant le corps de la réponse ; aucun secret
    (token, clé, mot de passe) dans le code ni dans Git : tout passe par des variables d'environnement.
    Ce fichier n'en contient aucun : il peut être commité tel quel.

Installation, sous Linux ou WSL
    Dans ~/aforp-python, venv activé ; data/inventory.yaml est là depuis le lab 2.3.
    Labo Docker démarré : cd ~/lab && docker compose start && bash scripts/check_lab.sh   (17 OK)
    Bibliothèques, au fil des labs, puis pip freeze > requirements.txt :
        4.2 : pip install fastapi uvicorn          4.3 : pip install docker
        4.4 : pip install boto3                    4.5 : pip install prometheus-client
    Secrets : voir enonce4.pdf, « Les secrets du jour ». Ils vont dans .env (jamais commité), puis :
        set -a; source .env; set +a
        STATUS_API_TOKEN (lab 4.1) ; AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY et
        S3_ENDPOINT_URL=http://127.0.0.1:9000 (lab 4.4) ; OPS_WEBHOOK_URL (lab 4.5)
    Puis copier lab4.py à la racine du projet, à côté du dossier data/.

Lab  Trous          Commandes de contrôle
4.1  TODO 1 à 11    python lab4.py api --create-incidents; echo "code=$?"          (2 dégradés, code=1)
                    STATUS_API_TOKEN=mauvais python lab4.py api; echo "code=$?"     (403, code=2)
4.2  TODO 12 à 16   python lab4.py serve, puis dans un second terminal :
                    curl -s "http://127.0.0.1:8090/checks?env=dev"                  ({"ok":true, …})
                    curl -s "http://127.0.0.1:8090/inventory?env=nope"              (erreur 404 et son détail)
4.3  TODO 17 à 21   docker stop lab-redis && python lab4.py docker --restart        (lab-redis relancé)
                    python lab4.py docker --logs lab-status-api                     (bonus : 5 lignes)
4.4  TODO 22 à 29   mkdir -p config && echo "port=8080" > config/app.conf
                    for i in 1 2 3 4 5 6 7; do python lab4.py backup config; sleep 1; done
                                                                                    (5 sauvegardes gardées)
4.5  TODO 30 à 35   docker stop lab-redis
                    python lab4.py health --env dev --notify; echo "code=$?"        (code=1, alerte reçue)
                    docker start lab-redis && python lab4.py exporter --env dev & sleep 2
                    curl -s http://127.0.0.1:9105/metrics | grep ^opstoolkit_       (2 métriques par cible)

Vérifier les fonctions avec les exemples des docstrings (sans le labo Docker)
    python -m doctest lab4.py
    Une fausse API de statut et un faux stockage S3, en mémoire, remplacent le labo. Les exemples des
    labs 4.4 et 4.5 demandent boto3 et prometheus-client. Aucun affichage : tous les exemples passent.
    Sinon, doctest montre l'exemple en échec, le résultat attendu et le résultat obtenu.

Codes retour : 0 = tout va bien, 1 = une cible est KO (composant dégradé, conteneur arrêté, port en échec),
2 = erreur d'usage, de configuration ou d'appel (convention d'OpsToolkit).
"""
# argparse : lecture des sous-commandes et des options de la ligne de commande
import argparse
# hashlib : empreinte SHA-256 des archives (lab 4.4)
import hashlib
# json : corps des réponses de la fausse API de statut, pour les exemples
import json
# logging : messages de suivi sur la sortie d'erreur, distincts du résultat affiché par print
import logging
# os : variables d'environnement, où se lisent tous les secrets du jour
import os
# socket : connexions TCP des tests de ports (socle du jour 3)
import socket
# sys : sys.exit transmet le code retour au shell
import sys
# tarfile : archives .tar.gz (lab 4.4)
import tarfile
# threading : la fausse API de statut tourne dans un thread, pour les exemples
import threading
# time : mesure des durées (socle du jour 3) et pause entre deux mesures de l'exporteur (lab 4.5)
import time
# ThreadPoolExecutor : tests de ports en parallèle (socle du jour 3)
from concurrent.futures import ThreadPoolExecutor
# datetime : date et heure dans le nom des archives (lab 4.4)
# (noqa : tant que les trous sont ouverts, ce module ne sert pas encore ; ruff --fix ne doit pas le retirer)
from datetime import datetime  # noqa: F401
# Serveur HTTP de la bibliothèque standard : la fausse API de statut des exemples
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
# Path : chemins de fichiers sous forme d'objets
from pathlib import Path
# SimpleNamespace : objet à attributs libres, pour imiter client.meta du vrai client S3
from types import SimpleNamespace
# Découpage d'une URL et de ses paramètres, dans la fausse API de statut
from urllib.parse import parse_qs, urlsplit

# requests : requêtes HTTP (labs 4.1 et 4.5), installé depuis le jour 1
import requests
# yaml, fourni par le paquet PyYAML : lecture de l'inventaire (jour 2)
import yaml

# fastapi, uvicorn, docker, boto3 et prometheus_client sont importés DANS les fonctions qui s'en servent :
# chaque lab s'installe au fil de la journée, et les labs précédents doivent fonctionner sans eux.

# Journal propre à ce fichier ; main() règle son niveau et son format
log = logging.getLogger("lab4")
# Champs obligatoires de chaque serveur de l'inventaire YAML (jour 2)
REQUIRED_KEYS = {"name", "host", "role", "ports"}


# ======================================================================================================
# Socle des jours 2 et 3 : inventaire et tests de ports. Déjà complet, rien à modifier.
# ======================================================================================================

# Exception métier : elle hérite d'Exception, comme InventaireInvalide au jour 1
class InventoryError(Exception):
    """Inventaire YAML absent, mal formé ou incomplet, ou environnement inconnu (jour 2, déjà complet).

    main() l'attrape pour afficher un message clair et renvoyer le code 2.
    """


# path accepte un texte ou un Path ; la fonction renvoie le contenu du YAML sous forme de dictionnaire
def load_inventory(path: str | Path) -> dict:
    """Charge l'inventaire YAML et vérifie sa structure (jour 2, déjà complet).

    Paramètres :
        path : chemin du fichier YAML ; la ligne de commande passe « data/inventory.yaml » par défaut.

    Renvoie :
        Le contenu du fichier : {"environments": {nom: {"servers": [serveur, …]}, …}}.

    Lève :
        InventoryError : fichier introuvable, YAML invalide, clé « environments » absente,
        environnement vide, ou serveur sans name, host, role ou ports.
    """
    # Bloc surveillé : les erreurs de lecture deviennent des InventoryError
    try:
        # Ouverture en lecture, en UTF-8
        with open(path, encoding="utf-8") as f:
            # safe_load ne crée que des objets simples : jamais yaml.load sur un fichier
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
            # Champs obligatoires absents : différence de deux ensembles
            missing = REQUIRED_KEYS - server.keys()
            # Un ensemble non vide est « vrai » : au moins un champ manque
            if missing:
                # sorted donne un message stable, par exemple ['host', 'ports']
                raise InventoryError(f"{env}, serveur n°{i} : champs manquants {sorted(missing)}")
    # L'inventaire est valide
    return data


# env vaut None par défaut : tous les environnements ; « str | None » signifie « texte, ou None »
def servers_of(inventory: dict, env: str | None = None) -> list[dict]:
    """Renvoie la liste à plat des serveurs, éventuellement filtrée par environnement (jour 2, déjà complet).

    Chaque serveur renvoyé est une copie qui porte en plus la clé « env » ; l'inventaire
    lui-même n'est pas modifié.

    Paramètres :
        inventory : inventaire chargé par load_inventory().
        env : nom d'un environnement (dev, recette, prod), ou None pour tous.

    Renvoie :
        La liste des serveurs, chacun avec la clé « env » en plus.

    Lève :
        InventoryError : l'environnement demandé n'existe pas.
    """
    # Raccourci vers le dictionnaire des environnements
    envs = inventory["environments"]
    # Un environnement demandé mais absent de l'inventaire est une erreur de configuration
    if env is not None and env not in envs:
        # join liste les environnements disponibles, séparés par des virgules
        raise InventoryError(f"Environnement inconnu : {env} (disponibles : {', '.join(envs)})")
    # Environnements à parcourir : celui demandé, ou tous
    selected = [env] if env else list(envs)
    # Liste à plat des serveurs
    result = []
    # Parcours des environnements retenus
    for e in selected:
        # Parcours de leurs serveurs ; « or [] » couvre une clé servers absente ou vide
        for s in envs[e].get("servers") or []:
            # Copie du serveur, avec la clé "env" en plus ; ** recopie toutes les clés de s
            result.append({**s, "env": e})
    # Renvoi de la liste
    return result


# Le résultat est un couple : (le port répond ?, temps de connexion en ms, ou None)
def port_check(host: str, port: int, timeout: float = 2.0) -> tuple[bool, int | None]:
    """Teste une connexion TCP vers host:port et mesure son temps d'établissement (jour 3, déjà complet).

    Renvoie :
        (True, durée en millisecondes arrondie à l'entier) si le port accepte la connexion ;
        (False, None) sinon : refus, délai dépassé ou nom inconnu.
    """
    # Top départ du chronomètre ; perf_counter ne recule jamais, contrairement à l'horloge du système
    start = time.perf_counter()
    # Bloc surveillé : refus, délai dépassé et nom inconnu lèvent tous une OSError
    try:
        # Connexion refermée dès la sortie du bloc with
        with socket.create_connection((host, port), timeout=timeout):
            # Durée écoulée, en millisecondes
            return True, round((time.perf_counter() - start) * 1000)
    # Toutes les erreurs réseau dérivent d'OSError
    except OSError:
        # Le port ne répond pas : pas de durée
        return False, None


# workers est le nombre de threads : 1 pour tester en séquence
def check_targets(servers: list[dict], workers: int = 10, timeout: float = 2.0) -> list[dict]:
    """Teste tous les ports de tous les serveurs, en parallèle (jour 3, déjà complet).

    Renvoie :
        Un résultat par port, dans l'ordre des serveurs puis de leurs ports :
        {"name": nom, "host": hôte, "port": port, "ok": True ou False, "ms": durée en ms ou None}.
    """
    # Un triplet (nom, hôte, port) pour chaque port de chaque serveur
    jobs = [(s["name"], s["host"], port) for s in servers for port in s["ports"]]

    # Le travail d'un thread : tester un port et mettre le résultat en forme
    def one(job: tuple[str, str, int]) -> dict:
        """Teste un triplet (nom, hôte, port) ; renvoie le dictionnaire de résultat."""
        # Déballage du triplet en trois variables
        name, host, port = job
        # Test du port, avec le délai demandé
        ok, ms = port_check(host, port, timeout)
        # Résultat complet
        return {"name": name, "host": host, "port": port, "ok": ok, "ms": ms}

    # Groupe de threads ; map garde l'ordre des jobs
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        # list() récupère tous les résultats avant la sortie du bloc
        return list(pool.map(one, jobs))


# ======================================================================================================
# Outils des exemples : une fausse API de statut et un faux stockage S3. Déjà complets, rien à modifier.
# Ils remplacent le labo Docker dans les docstrings, pour que python -m doctest lab4.py tourne partout.
# ======================================================================================================

# Les 6 composants de l'API de statut du labo, avec les mêmes statuts
FAKE_COMPONENTS = [
    {"id": 1, "name": "site-web", "status": "operational"},
    {"id": 2, "name": "api-commandes", "status": "operational"},
    {"id": 3, "name": "paiements", "status": "degraded_performance"},
    {"id": 4, "name": "base-clients", "status": "operational"},
    {"id": 5, "name": "recherche", "status": "major_outage"},
    {"id": 6, "name": "stockage-s3", "status": "operational"},
]


# Une API HTTP minimale, servie par la bibliothèque standard dans un thread
class FakeStatusAPI:
    """Fausse API de statut, locale, qui imite lab-status-api pour les exemples (déjà complète).

    Mêmes routes et mêmes réponses que le labo : /health, /components (paginé, token exigé),
    POST /incidents (token exigé), /flaky (toujours 500), /slow (répond après 2 s).
    Elle démarre sur un port libre ; son adresse est dans l'attribut url. stop() l'arrête.

    Paramètres :
        token : token accepté, « aforp-test » par défaut.
    """

    # Démarrage du serveur sur un port libre, dans un thread qui s'arrêtera avec le programme
    def __init__(self, token: str = "aforp-test"):
        """Démarre la fausse API ; son adresse est ensuite dans self.url."""
        # Token accepté et incidents créés depuis le démarrage
        self.token, self.incidents = token, []
        # Référence à cette API, utilisée par le gestionnaire de requêtes ci-dessous
        api = self

        # Gestionnaire : une instance par requête reçue
        class Handler(BaseHTTPRequestHandler):
            """Répond aux requêtes comme lab-status-api."""

            # Pas de ligne de journal par requête : les exemples restent lisibles
            def log_message(self, *args):
                """Ne journalise rien."""

            # Envoi d'une réponse JSON avec son code HTTP
            def send_json(self, code: int, body) -> None:
                """Envoie body en JSON avec le code HTTP code."""
                # Corps en octets
                data = json.dumps(body).encode()
                # Ligne de statut, en-têtes, puis corps
                try:
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                # Client parti avant la réponse (délai dépassé sur /slow) : rien à faire
                except ConnectionError:
                    pass

            # Contrôle du token : 401 sans en-tête, 403 avec un mauvais token
            def authorized(self) -> bool:
                """Renvoie True si le token est bon ; sinon, répond 401 ou 403 et renvoie False."""
                # En-tête d'authentification envoyé par le client
                header = self.headers.get("Authorization")
                # Pas d'en-tête : 401
                if header is None:
                    self.send_json(401, {"detail": "Token manquant"})
                    return False
                # Mauvais token : 403
                if header != f"Bearer {api.token}":
                    self.send_json(403, {"detail": "Token invalide"})
                    return False
                # Token accepté
                return True

            # Requêtes GET
            def do_GET(self):
                """Routes /health, /components, /flaky et /slow."""
                # Chemin et paramètres de requête
                url = urlsplit(self.path)
                query = parse_qs(url.query)
                # Route publique de santé
                if url.path == "/health":
                    return self.send_json(200, {"status": "ok"})
                # Route qui échoue toujours
                if url.path == "/flaky":
                    return self.send_json(500, {"detail": "Erreur interne simulée"})
                # Route lente : 2 s de pause avant de répondre
                if url.path == "/slow":
                    time.sleep(2)
                    return self.send_json(200, {"status": "ok", "delay_s": 2})
                # Liste paginée des composants, réservée aux clients authentifiés
                if url.path == "/components":
                    if not self.authorized():
                        return None
                    # Numéro de page et taille de page, 1 et 4 par défaut comme au labo
                    page = int(query.get("page", ["1"])[0])
                    per_page = int(query.get("per_page", ["4"])[0])
                    # Nombre de pages, arrondi au-dessus
                    pages = max(1, -(-len(FAKE_COMPONENTS) // per_page))
                    # Page au-delà de la dernière : 404, comme au labo
                    if page > pages:
                        return self.send_json(404, {"detail": "Page inexistante"})
                    # Tranche de composants de cette page
                    items = FAKE_COMPONENTS[(page - 1) * per_page:page * per_page]
                    return self.send_json(200, {"items": items, "page": page, "pages": pages,
                                                "total": len(FAKE_COMPONENTS)})
                # Toute autre route : 404
                return self.send_json(404, {"detail": "Not Found"})

            # Requêtes POST
            def do_POST(self):
                """Route POST /incidents : crée un incident et le renvoie avec son numéro."""
                # Seule route POST connue
                if self.path != "/incidents":
                    return self.send_json(404, {"detail": "Not Found"})
                if not self.authorized():
                    return None
                # Corps JSON envoyé par le client
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                # Incident numéroté à partir de 1, comme au labo
                incident = {"id": len(api.incidents) + 1, **body}
                api.incidents.append(incident)
                return self.send_json(201, incident)

        # Serveur sur un port libre (port 0 : le système en choisit un)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        # Adresse complète de l'API
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        # Le serveur répond dans un thread de fond
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    # Arrêt du serveur et libération du port
    def stop(self) -> None:
        """Arrête la fausse API."""
        # Fin de la boucle du serveur, puis fermeture de son port
        self.server.shutdown()
        self.server.server_close()


# Un dictionnaire par bucket, qui associe chaque clé à la taille et aux métadonnées de l'objet
class MemoryS3:
    """Faux client S3 en mémoire, pour les exemples du lab 4.4 (déjà complet).

    Il imite les méthodes du client boto3 utilisées dans ce fichier : head_bucket, create_bucket,
    upload_file, list_objects_v2, head_object et delete_object. put() dépose un objet vide.

    Paramètres :
        buckets : noms des buckets qui existent dès le départ.
    """

    # Buckets de départ, tous vides
    def __init__(self, buckets: tuple[str, ...] = ()):
        """Crée le faux stockage avec les buckets donnés."""
        # {bucket: {clé: {"Size": taille, "Metadata": {…}}}}
        self.buckets = {name: {} for name in buckets}
        # Région, lue par ensure_bucket() comme client.meta.region_name
        self.meta = SimpleNamespace(region_name="us-east-1")

    # Comme boto3 : ClientError si le bucket n'existe pas
    def head_bucket(self, Bucket: str) -> dict:
        """Vérifie que le bucket existe."""
        if Bucket not in self.buckets:
            # Import ici : botocore n'est installé qu'au lab 4.4, avec boto3
            from botocore.exceptions import ClientError
            raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket")
        return {}

    # Création du bucket ; CreateBucketConfiguration est accepté et ignoré
    def create_bucket(self, Bucket: str, **kwargs) -> dict:
        """Crée le bucket s'il n'existe pas."""
        self.buckets.setdefault(Bucket, {})
        return {}

    # Envoi d'un fichier local ; ExtraArgs peut contenir les métadonnées
    def upload_file(self, Filename: str, Bucket: str, Key: str, ExtraArgs: dict | None = None) -> None:
        """Enregistre l'objet Key avec la taille du fichier et ses métadonnées."""
        metadata = dict((ExtraArgs or {}).get("Metadata", {}))
        self.buckets[Bucket][Key] = {"Size": Path(Filename).stat().st_size, "Metadata": metadata}

    # Raccourci des exemples : un objet vide, sans fichier local
    def put(self, Bucket: str, Key: str) -> None:
        """Dépose un objet vide sous la clé Key."""
        self.buckets[Bucket][Key] = {"Size": 0, "Metadata": {}}

    # Comme boto3 : pas de clé « Contents » quand aucun objet ne correspond
    def list_objects_v2(self, Bucket: str, Prefix: str = "") -> dict:
        """Liste les objets dont la clé commence par Prefix, triés par clé."""
        contents = [{"Key": k, "Size": v["Size"]} for k, v in sorted(self.buckets[Bucket].items())
                    if k.startswith(Prefix)]
        return {"Contents": contents} if contents else {}

    # Métadonnées d'un objet
    def head_object(self, Bucket: str, Key: str) -> dict:
        """Renvoie {"Metadata": {…}} pour l'objet Key."""
        return {"Metadata": self.buckets[Bucket][Key]["Metadata"]}

    # Suppression, sans erreur si l'objet n'existe pas, comme S3
    def delete_object(self, Bucket: str, Key: str) -> dict:
        """Supprime l'objet Key."""
        self.buckets[Bucket].pop(Key, None)
        return {}


# ======================================================================================================
# Lab 4.1 — Consommer l'API de statut
# ======================================================================================================

# Exception métier, comme InventoryError : main() l'attrape pour afficher un message clair et renvoyer 2
class StatusApiError(Exception):
    """Erreur d'appel à l'API de statut, avec un message lisible par un opérateur (lab 4.1).

    Token absent ou refusé, ressource introuvable, erreur du serveur, délai dépassé ou API injoignable.
    """


# Un client regroupe l'adresse de l'API, le token, le délai et une session HTTP réutilisée
class StatusClient:
    """Client de l'API de statut de CloudNova (lab 4.1).

    Paramètres :
        base_url : adresse de l'API, « http://127.0.0.1:8000 » au labo.
        token : token d'accès ; None (défaut) pour le lire dans STATUS_API_TOKEN.
        timeout : délai maximal de chaque appel, en secondes.

    Lève :
        StatusApiError : aucun token, ni en paramètre ni dans l'environnement.

    Exemples (sans réseau) :
        >>> client = StatusClient(token="exemple")
        >>> client.session.headers["Authorization"]
        'Bearer exemple'
        >>> _ = os.environ.pop("STATUS_API_TOKEN", None)
        >>> try:
        ...     StatusClient()
        ... except StatusApiError as exc:
        ...     print(exc)
        Variable STATUS_API_TOKEN absente : export STATUS_API_TOKEN=...
        >>> os.environ["STATUS_API_TOKEN"] = "lu-dans-l-environnement"
        >>> StatusClient().token
        'lu-dans-l-environnement'
        >>> del os.environ["STATUS_API_TOKEN"]
    """

    # self est l'objet en construction ; les paramètres ont tous une valeur par défaut
    def __init__(self, base_url: str = "http://127.0.0.1:8000", token: str | None = None,
                 timeout: float = 3.0):
        """Prépare le client : adresse, token, délai et session authentifiée."""
        # rstrip("/") évite un double « // » quand on ajoute le chemin
        self.base_url = base_url.rstrip("/")
        # TODO 1 : si token vaut None, le lire dans la variable d'environnement STATUS_API_TOKEN.
        # Aide : diapositive 51, encadré « Côté Python » ; même principe qu'au TODO 26 du lab 3.5.
        # Réponse : on garde le token reçu ; s'il vaut None, os.environ.get() le lit dans l'environnement
        # (None si la variable n'existe pas, ce qui déclenche le message d'erreur juste en dessous).
        self.token = token if token is not None else os.environ.get("STATUS_API_TOKEN")
        # Sans token, inutile d'aller plus loin : le message dit quoi faire, sans afficher de secret
        if not self.token:
            raise StatusApiError("Variable STATUS_API_TOKEN absente : export STATUS_API_TOKEN=...")
        # Délai de chaque appel
        self.timeout = timeout
        # Une session réutilise la connexion et porte des en-têtes communs à toutes les requêtes
        self.session = requests.Session()
        # TODO 2 : chaque requête de la session doit porter l'en-tête Authorization « Bearer <token> ».
        # Aide : diapositive 52, ligne « En-têtes » ; session.headers se remplit comme un dictionnaire.
        # Réponse : session.headers est un dictionnaire d'en-têtes envoyés avec CHAQUE requête de la session ;
        # le format attendu par l'API est « Bearer » + espace + token.
        self.session.headers["Authorization"] = f"Bearer {self.token}"

    # Toutes les requêtes passent par ici : délai, puis traduction de chaque erreur en message utile
    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Envoie une requête à l'API et vérifie son code HTTP avant de rendre la réponse (lab 4.1).

        Paramètres :
            method : méthode HTTP, « GET » ou « POST ».
            path : chemin, par exemple « /components ».
            kwargs : options transmises à requests, par exemple params= ou json=.

        Renvoie :
            La réponse, seulement si son code est un succès (2xx).

        Lève :
            StatusApiError : délai dépassé, API injoignable, 401, 403, 404, 5xx ou autre erreur.

        Exemples (une fausse API locale remplace lab-status-api ; son token est « aforp-test ») :
            >>> api = FakeStatusAPI()
            >>> def essai(client, path):
            ...     try:
            ...         return client._request("GET", path).status_code
            ...     except StatusApiError as exc:
            ...         print(exc)
            >>> essai(StatusClient(api.url, token="aforp-test"), "/components")
            200
            >>> essai(StatusClient(api.url, token="mauvais"), "/components")
            403 sur /components : token refusé
            >>> essai(StatusClient(api.url, token="aforp-test"), "/inconnu")
            404 sur /inconnu : ressource introuvable
            >>> essai(StatusClient(api.url, token="aforp-test"), "/flaky")
            500 sur /flaky : erreur côté serveur
            >>> essai(StatusClient(api.url, token="aforp-test", timeout=0.5), "/slow")
            Pas de réponse en 0.5 s sur /slow
            >>> api.stop()
            >>> essai(StatusClient(api.url, token="aforp-test"), "/health")  # doctest: +ELLIPSIS
            API injoignable (http://127.0.0.1:...) : conteneur démarré ?
        """
        # Bloc surveillé : les échecs réseau deviennent des StatusApiError
        try:
            # TODO 3 : envoyer la requête method vers base_url + path PAR LA SESSION, avec le timeout du
            #          client, en transmettant **kwargs (params=, json=…).
            # Aide : diapositive 53, règle 1 ; Session a une méthode request(method, url, …) qui accepte les
            #        mêmes options que requests.get.
            # Réponse : session.request(méthode, url, …) envoie GET ou POST selon method ; timeout borne l'attente ;
            # **kwargs transmet tel quel ce que l'appelant a passé (params=, json=…).
            response = self.session.request(method, self.base_url + path, timeout=self.timeout, **kwargs)
        # Délai dépassé (à placer avant ConnectionError : un délai de connexion est les deux à la fois)
        except requests.Timeout as exc:
            raise StatusApiError(f"Pas de réponse en {self.timeout} s sur {path}") from exc
        # Rien n'écoute à cette adresse : le plus souvent, le conteneur est arrêté
        except requests.ConnectionError as exc:
            raise StatusApiError(f"API injoignable ({self.base_url}) : conteneur démarré ?") from exc
        # Message lisible pour chaque erreur du client que l'on sait expliquer
        messages = {401: "token manquant", 403: "token refusé", 404: "ressource introuvable"}
        # TODO 4 : condition vraie si le code HTTP de la réponse fait partie des clés de messages.
        # Aide : l'opérateur in teste la présence d'une clé dans un dictionnaire.
        # Réponse : « in » sur un dictionnaire teste ses clés : vrai pour 401, 403 ou 404.
        if response.status_code in messages:
            # Par exemple « 403 sur /components : token refusé »
            raise StatusApiError(f"{response.status_code} sur {path} : {messages[response.status_code]}")
        # TODO 5 : condition vraie pour toute erreur côté serveur (famille 5xx).
        # Aide : diapositive 52, ligne « Statut ».
        # Réponse : les erreurs serveur sont les codes 500 à 599 ; >= 500 suffit, il n'existe pas de code 600.
        if response.status_code >= 500:
            # Par exemple « 500 sur /flaky : erreur côté serveur »
            raise StatusApiError(f"{response.status_code} sur {path} : erreur côté serveur")
        # Toute autre erreur (422 si le corps envoyé est invalide…) : message générique, jamais de trace
        if not response.ok:
            raise StatusApiError(f"{response.status_code} sur {path} : requête refusée")
        # Succès : l'appelant peut lire le corps sans risque
        return response

    # Une API renvoie rarement toute une liste d'un coup : on demande les pages une par une
    def components(self, per_page: int = 4) -> list[dict]:
        """Renvoie tous les composants, en suivant la pagination (lab 4.1).

        Paramètres :
            per_page : nombre de composants demandés par page ; le résultat ne doit pas en dépendre.

        Renvoie :
            La liste des composants {"id", "name", "status"}, toutes pages confondues.

        Exemples (fausse API locale) :
            >>> api = FakeStatusAPI()
            >>> client = StatusClient(api.url, token="aforp-test")
            >>> [c["name"] for c in client.components()]
            ['site-web', 'api-commandes', 'paiements', 'base-clients', 'recherche', 'stockage-s3']
            >>> len(client.components(per_page=1)), len(client.components(per_page=50))
            (6, 6)
            >>> api.stop()
        """
        # Composants déjà reçus, et numéro de la page à demander
        items, page = [], 1
        # Boucle sans fin apparente : elle s'arrête par le return de la dernière page
        while True:
            # TODO 6 : demander la page `page` de /components, avec per_page composants par page, et lire
            #          le JSON de la réponse.
            # Aide : les paramètres de requête se passent dans params= (un dictionnaire) ; _request renvoie
            #        la réponse, dont .json() donne le corps.
            # Réponse : params= ajoute ?page=…&per_page=… à l'URL ; _request vérifie le code HTTP AVANT qu'on lise
            # le corps (règle du jour), puis .json() transforme le corps en dictionnaire.
            data = self._request("GET", "/components", params={"page": page, "per_page": per_page}).json()
            # TODO 7 : ajouter les composants de cette page à items.
            # Aide : data["items"] est une liste ; cherchez la méthode de list qui ajoute plusieurs éléments.
            # Réponse : extend ajoute chaque élément de la liste ; append ajouterait la liste entière comme UN élément.
            items.extend(data["items"])
            # TODO 8 : condition vraie quand la page courante est la dernière.
            # Aide : diapositive 53, règle 4 ; la réponse donne le nombre total de pages dans data["pages"].
            # Réponse : quand le numéro de page atteint le nombre total de pages, on a tout reçu : on s'arrête.
            if page >= data["pages"]:
                # Dernière page : la liste est complète
                return items
            # Page suivante
            page += 1

    # Les composants qui ne sont pas « operational »
    def degraded(self) -> list[dict]:
        """Renvoie les composants dégradés ou en panne (lab 4.1).

        Exemple (fausse API locale) :
            >>> api = FakeStatusAPI()
            >>> [(c["name"], c["status"]) for c in StatusClient(api.url, token="aforp-test").degraded()]
            [('paiements', 'degraded_performance'), ('recherche', 'major_outage')]
            >>> api.stop()
        """
        # TODO 9 : renvoyer les composants dont le statut n'est pas « operational ».
        # Aide : une compréhension de liste avec un if, sur le résultat de components().
        # Réponse : compréhension de liste filtrée : on garde chaque composant c dont le statut n'est pas
        # « operational » (donc degraded_performance, major_outage…).
        return [c for c in self.components() if c["status"] != "operational"]

    # severity vaut « minor » par défaut ; cmd_api passe « major »
    def create_incident(self, component: str, title: str, severity: str = "minor") -> dict:
        """Crée un incident sur l'API (POST /incidents) et le renvoie, avec son numéro (lab 4.1).

        Exemple (fausse API locale) :
            >>> api = FakeStatusAPI()
            >>> client = StatusClient(api.url, token="aforp-test")
            >>> client.create_incident("recherche", "recherche en panne", "major")
            {'id': 1, 'component': 'recherche', 'title': 'recherche en panne', 'severity': 'major'}
            >>> client.create_incident("paiements", "paiements lents")["id"]
            2
            >>> api.stop()
        """
        # Corps de la requête, envoyé en JSON
        payload = {"component": component, "title": title, "severity": severity}
        # TODO 10 : envoyer payload en JSON par une requête POST sur /incidents, et renvoyer l'incident
        #           créé, c'est-à-dire le JSON de la réponse.
        # Aide : diapositive 52, ligne « Méthode » ; json= envoie un dictionnaire en JSON.
        # Réponse : json= envoie le dictionnaire en JSON (et l'en-tête Content-Type) ; l'API renvoie l'incident
        # créé avec son numéro, que .json() transforme en dictionnaire.
        return self._request("POST", "/incidents", json=payload).json()


# ======================================================================================================
# Lab 4.2 — Exposer OpsToolkit avec FastAPI
# ======================================================================================================

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

    # Chemin de l'inventaire : paramètre, sinon variable d'environnement, sinon valeur par défaut
    path = inventory_path or os.environ.get("OPS_INVENTORY", "data/inventory.yaml")
    # L'application ; title et version apparaissent dans /docs
    app = FastAPI(title="OpsToolkit API", version="1.0")

    # TODO 12 : associer la fonction health aux requêtes GET sur le chemin /health.
    # Aide : diapositive 55 : un décorateur de app, placé juste au-dessus de la fonction.
    # Réponse : le décorateur @app.get(chemin) dit à FastAPI d'appeler la fonction en dessous pour GET /health.
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
            # TODO 13 : répondre 404, avec le message de l'exception comme détail, au lieu d'une liste vide.
            # Aide : diapositive 55 ; HTTPException se lève avec raise, et prend status_code et detail.
            # Réponse : lever HTTPException fait répondre FastAPI avec ce code et {"detail": message} ;
            # « from exc » garde l'erreur d'origine pour le débogage.
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Même paramètre env que /inventory
    @app.get("/checks")
    def checks(env: str | None = None):
        """Test des ports de l'environnement, avec un booléen global."""
        # Bloc surveillé : même traitement de l'environnement inconnu que dans inventory()
        try:
            # TODO 14 : tester tous les ports des serveurs de l'environnement env, avec check_targets().
            # Aide : même chargement que dans inventory(), puis un appel de plus (socle du jour 3).
            # Réponse : on charge l'inventaire, on filtre par env (servers_of), puis on teste tous les ports.
            results: list[dict] = check_targets(servers_of(load_inventory(path), env))
        # Environnement inconnu : 404
        except InventoryError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        # TODO 15 : renvoyer {"ok": …, "results": results} ; ok n'est vrai que si TOUTES les cibles répondent.
        # Aide : une fonction intégrée teste « tous » : c'est la sœur de any() (TODO 22 du lab 3.3).
        # Réponse : all() vaut True seulement si TOUTES les cibles ont ok=True (et True pour une liste vide).
        return {"ok": all(r["ok"] for r in results), "results": results}

    # Application prête
    return app


# ======================================================================================================
# Lab 4.3 — Piloter les conteneurs avec le SDK Docker
# ======================================================================================================

# prefix filtre les conteneurs du labo : lab-web, lab-db, lab-redis…
def lab_containers(prefix: str = "lab-") -> list[dict]:
    """Liste les conteneurs dont le nom commence par prefix, arrêtés compris (lab 4.3).

    Paramètres :
        prefix : début du nom des conteneurs retenus.

    Renvoie :
        Une liste triée par nom : [{"name": …, "status": "running" ou "exited"…, "image": …}, …].

    Résultat attendu après docker stop lab-redis (les autres conteneurs sont « running ») :
        [{'name': 'lab-db', 'status': 'running', 'image': 'postgres:16-alpine'}, …,
         {'name': 'lab-redis', 'status': 'exited', 'image': 'redis:7-alpine'}, …]
    """
    # Import ici : le SDK Docker n'est installé qu'au lab 4.3
    import docker

    # Client qui parle au démon Docker par son socket, comme la commande docker
    client = docker.from_env()
    # TODO 17 : lister TOUS les conteneurs, y compris les conteneurs arrêtés.
    # Aide : diapositive 56, « L'essentiel » ; sans option, list() ne renvoie que ceux en marche (docker ps).
    # Réponse : all=True inclut les conteneurs arrêtés, comme docker ps -a.
    containers = client.containers.list(all=True)
    # Conteneurs retenus
    result = []
    # Parcours de tous les conteneurs du poste
    for c in containers:
        # TODO 18 : condition vraie si le nom du conteneur commence par prefix.
        # Aide : une méthode de str ; le nom est dans l'attribut name du conteneur.
        # Réponse : startswith() teste le début du nom : lab-web, lab-db… oui ; shopsecure_web non.
        if c.name.startswith(prefix):
            # Premier tag de l'image, par exemple « redis:7-alpine » ; « ? » si l'image n'a pas de tag
            image = c.image.tags[0] if c.image.tags else "?"
            # Nom, statut et image
            result.append({"name": c.name, "status": c.status, "image": image})
    # Ordre stable : par nom
    return sorted(result, key=lambda c: c["name"])


# Auto-remédiation : relancer ce qui est tombé
def restart_stopped(prefix: str = "lab-") -> list[str]:
    """Redémarre les conteneurs arrêtés dont le nom commence par prefix (lab 4.3).

    Paramètres :
        prefix : début du nom des conteneurs concernés.

    Renvoie :
        Les noms des conteneurs redémarrés ; liste vide si aucun n'était arrêté.

    Résultat attendu après docker stop lab-redis :
        ['lab-redis']
    """
    # Import ici, comme dans lab_containers()
    import docker

    # Client Docker
    client = docker.from_env()
    # Noms des conteneurs redémarrés
    restarted = []
    # TODO 19 : parcourir seulement les conteneurs arrêtés (statut « exited »).
    # Aide : diapositive 56 : list() accepte un filtre par statut, comme docker ps --filter status=exited.
    # Réponse : filters={"status": "exited"} ne garde que les conteneurs arrêtés ; all=True est nécessaire,
    # sinon list() ne regarde que les conteneurs en marche et n'en trouverait aucun d'arrêté.
    for c in client.containers.list(all=True, filters={"status": "exited"}):
        # Seulement les conteneurs du labo : jamais ceux des autres projets du poste
        if c.name.startswith(prefix):
            # TODO 20 : démarrer le conteneur c.
            # Aide : une méthode de l'objet conteneur, comme la commande docker start.
            # Réponse : c.start() fait la même chose que docker start <nom>.
            c.start()
            # Trace du redémarrage
            restarted.append(c.name)
    # Liste des conteneurs relancés
    return restarted


# Bonus du lab 4.3 : les dernières lignes du journal d'un conteneur
def container_logs(name: str, tail: int = 5) -> str:
    """Renvoie les tail dernières lignes du journal du conteneur name (bonus du lab 4.3).

    Lève :
        docker.errors.NotFound : aucun conteneur de ce nom ; cmd_docker en fait un message clair.
    """
    # Import ici, comme dans lab_containers()
    import docker

    # Client Docker
    client = docker.from_env()
    # TODO 21 (bonus) : renvoyer les tail dernières lignes du journal du conteneur name, en texte.
    # Aide : containers.get(name) donne le conteneur ; logs() accepte tail= et renvoie des octets : decode().
    # Réponse : get() trouve le conteneur par son nom ; logs(tail=5) renvoie les 5 dernières lignes en octets ;
    # decode() les transforme en texte (errors="replace" évite un plantage sur un caractère invalide).
    return client.containers.get(name).logs(tail=tail).decode(errors="replace")


# ======================================================================================================
# Lab 4.4 — Sauvegardes S3 / MinIO avec boto3
# ======================================================================================================

# Exception métier : main() l'attrape pour afficher un message clair et renvoyer le code 2
class BackupError(Exception):
    """Sauvegarde impossible : dossier introuvable ou erreur S3 (lab 4.4)."""


# Le même code parle à MinIO (au labo) ou à AWS (en production) : seule l'adresse change
def s3_client():
    """Crée un client S3 : MinIO si S3_ENDPOINT_URL est définie, sinon AWS (lab 4.4).

    Les identifiants ne sont jamais passés ici : boto3 les lit lui-même dans AWS_ACCESS_KEY_ID et
    AWS_SECRET_ACCESS_KEY.

    Renvoie :
        Un client boto3 « s3 ».
    """
    # Import ici : boto3 n'est installé qu'au lab 4.4
    # (noqa : boto3 ne sert qu'une fois le TODO 22 fermé ; ruff --fix ne doit pas le retirer)
    import boto3  # noqa: F401

    # Adresse de MinIO, ou None pour AWS ; « or None » transforme une variable vide en None
    endpoint = os.environ.get("S3_ENDPOINT_URL") or None
    # Région : us-east-1 pour MinIO, Paris (eu-west-3) pour AWS, sauf si AWS_DEFAULT_REGION est définie
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1" if endpoint else "eu-west-3")
    # TODO 22 : renvoyer un client « s3 » vers endpoint (MinIO), ou vers AWS si endpoint vaut None, dans
    #           la région region.
    # Aide : diapositive 57, encadré « boto3 » ; boto3.client accepte endpoint_url et region_name.
    #        En attendant, la valeur provisoire est le faux stockage en mémoire : rien n'arrive dans MinIO.
    return boto3.client("s3", endpoint_url=endpoint, region_name=region)


# dest_dir est le dossier où l'archive est créée, le dossier courant par défaut
def make_archive(folder: str | Path, dest_dir: str | Path = ".") -> Path:
    """Compresse un dossier en backup-AAAAMMJJ-HHMMSS.tar.gz (lab 4.4).

    Paramètres :
        folder : dossier à sauvegarder.
        dest_dir : dossier où créer l'archive.

    Renvoie :
        Le chemin de l'archive créée.

    Lève :
        BackupError : le dossier n'existe pas.

    Exemples (dossiers temporaires) :
        >>> import tempfile
        >>> src = Path(tempfile.mkdtemp()) / "config"
        >>> src.mkdir()
        >>> _ = (src / "app.conf").write_text("port=8080\\n")
        >>> archive = make_archive(src, dest_dir=tempfile.mkdtemp())
        >>> len(archive.name) == len("backup-AAAAMMJJ-HHMMSS.tar.gz") and archive.name.startswith("backup-2")
        True
        >>> with tarfile.open(archive) as tar:
        ...     tar.getnames()
        ['config', 'config/app.conf']
        >>> try:
        ...     make_archive("dossier-absent")
        ... except BackupError as exc:
        ...     print(exc)
        Dossier introuvable : dossier-absent
    """
    # Path, quel que soit le type reçu
    folder = Path(folder)
    # Dossier absent : erreur claire, avant de créer quoi que ce soit
    if not folder.is_dir():
        raise BackupError(f"Dossier introuvable : {folder}")
    # TODO 23 : nom de l'archive, backup-AAAAMMJJ-HHMMSS.tar.gz, avec la date et l'heure actuelles.
    # Aide : une f-string accepte un format de date après « : », par exemple f"{datetime.now():%Y}".
    name = f"backup-{datetime.now():%Y%m%d-%H%M%S}.tar.gz"
    # Chemin complet de l'archive
    archive = Path(dest_dir) / name
    # « w:gz » : écriture, compressée avec gzip ; le bloc with ferme l'archive
    with tarfile.open(archive, "w:gz") as tar:
        # TODO 24 : ajouter le dossier à l'archive, rangé sous son seul nom et non sous son chemin complet.
        # Aide : tar.add(…) a un paramètre arcname : le nom de l'élément dans l'archive.
        tar.add(folder, arcname=folder.name)
    # Chemin de l'archive créée
    return archive


# Empreinte d'un fichier, calculée par blocs : la mémoire reste faible, même pour une archive de 10 Go
def sha256(path: Path) -> str:
    """Calcule l'empreinte SHA-256 d'un fichier, en hexadécimal (lab 4.4).

    Exemple (un fichier qui contient « abc ») :
        >>> import tempfile
        >>> p = Path(tempfile.mkdtemp()) / "abc.txt"
        >>> _ = p.write_bytes(b"abc")
        >>> sha256(p)
        'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    """
    # Calculateur d'empreinte, nourri bloc par bloc
    digest = hashlib.sha256()
    # « rb » : lecture en octets, sans décodage
    with open(path, "rb") as f:
        # TODO 25 : lire le fichier par blocs de 64 Kio (65536 octets) jusqu'à la fin.
        # Aide : read(65536) renvoie b"" en fin de fichier ; iter(fonction, b"") s'arrête sur cette valeur.
        for chunk in iter(lambda: f.read(65536), b""):
            # Le bloc nourrit le calcul
            digest.update(chunk)
    # Empreinte en hexadécimal : 64 caractères
    return digest.hexdigest()


# Création à la demande : la première sauvegarde crée le bucket
def ensure_bucket(client, bucket: str) -> None:
    """Crée le bucket s'il n'existe pas encore (lab 4.4, déjà complet).

    Hors de la région us-east-1, AWS exige la région du bucket à sa création
    (sinon : IllegalLocationConstraintException).
    """
    # Import ici : botocore est installé avec boto3, au lab 4.4
    from botocore.exceptions import ClientError

    # head_bucket réussit si le bucket existe et nous est accessible
    try:
        client.head_bucket(Bucket=bucket)
    # Bucket absent : on le crée
    except ClientError:
        # Trace de la création
        log.info("Création du bucket %s", bucket)
        # Région du client
        region = client.meta.region_name
        # Hors us-east-1 : la région doit être précisée
        if region and region != "us-east-1":
            client.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": region})
        # us-east-1 (et MinIO) : pas de configuration
        else:
            client.create_bucket(Bucket=bucket)


# prefix range les sauvegardes « dans » backups/ : en S3, ce n'est qu'un début de clé
def upload(client, archive: Path, bucket: str, prefix: str = "backups/") -> str:
    """Envoie l'archive dans le bucket, avec son empreinte SHA-256 en métadonnée (lab 4.4).

    Renvoie :
        La clé de l'objet créé, par exemple « backups/backup-20261126-140744.tar.gz ».
    """
    # Clé de l'objet : préfixe et nom de l'archive
    key = prefix + archive.name
    # TODO 26 : envoyer le fichier archive dans bucket, sous la clé key, avec son empreinte SHA-256 dans la
    #           métadonnée « sha256 ».
    # Aide : diapositive 57 ; upload_file(fichier, bucket, clé, ExtraArgs={"Metadata": {…}}).
    client.upload_file(str(archive), bucket, key, ExtraArgs={"Metadata":{"sha256": sha256(archive)}})
    # Clé de l'objet envoyé
    return key


# Le nom des sauvegardes contient leur date : trier par clé, c'est trier par date
def list_backups(client, bucket: str, prefix: str = "backups/") -> list[dict]:
    """Liste les sauvegardes du bucket, de la plus ancienne à la plus récente (lab 4.4, déjà complet).

    Renvoie :
        [{"key": clé, "size": taille en octets}, …].
    """
    # Objets dont la clé commence par prefix
    response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    # « Contents » est absent quand aucun objet ne correspond
    objects = [{"key": o["Key"], "size": o["Size"]} for o in response.get("Contents", [])]
    # Tri chronologique, grâce à l'horodatage dans le nom
    return sorted(objects, key=lambda o: o["key"])


# keep vaut 5 par défaut : les 5 sauvegardes les plus récentes sont gardées
def rotate(client, bucket: str, keep: int = 5, prefix: str = "backups/") -> list[str]:
    """Supprime les sauvegardes les plus anciennes au-delà de keep (lab 4.4).

    Paramètres :
        client : client S3 (boto3, ou MemoryS3 dans les exemples).
        bucket : nom du bucket.
        keep : nombre de sauvegardes à garder ; 0 ou moins pour ne rien supprimer.

    Renvoie :
        Les clés supprimées, de la plus ancienne à la plus récente.

    Exemples (faux stockage en mémoire, 7 sauvegardes du 20 au 26 novembre) :
        >>> s3 = MemoryS3(buckets=("b",))
        >>> for day in range(20, 27):
        ...     s3.put("b", f"backups/backup-202611{day}-120000.tar.gz")
        >>> rotate(s3, "b", keep=5)
        ['backups/backup-20261120-120000.tar.gz', 'backups/backup-20261121-120000.tar.gz']
        >>> [o["key"][15:23] for o in list_backups(s3, "b")]
        ['20261122', '20261123', '20261124', '20261125', '20261126']
        >>> rotate(s3, "b", keep=5), rotate(s3, "b", keep=10)
        ([], [])
    """
    # Sauvegardes existantes, de la plus ancienne à la plus récente
    backups = list_backups(client, bucket, prefix)
    # TODO 27 : clés des sauvegardes à supprimer : toutes, sauf les keep plus récentes (les dernières de la
    #           liste). Avec keep plus grand que le nombre de sauvegardes, rien n'est supprimé.
    # Aide : une tranche avec un indice négatif, puis une compréhension de liste qui garde o["key"].
    old: list[str] = [o["key"] for o in backups[:-keep]] if keep > 0 else []
    # Suppression de chaque ancienne sauvegarde
    for key in old:
        # TODO 28 : supprimer l'objet key du bucket.
        # Aide : une méthode du client boto3, avec les paramètres nommés Bucket= et Key=.
        client.delete_object(Bucket=bucket, Key=key)
    # Clés supprimées
    return old


# client vaut None par défaut : le vrai client S3 ; les exemples passent un MemoryS3
def backup(folder: str | Path, bucket: str, keep: int = 5, client=None, dest_dir: str | Path = ".") -> dict:
    """Archive un dossier, l'envoie dans le bucket, puis applique la rotation (lab 4.4).

    L'archive locale est supprimée dans tous les cas, que l'envoi réussisse ou non.

    Paramètres :
        folder : dossier à sauvegarder.
        bucket : bucket de destination, créé s'il n'existe pas.
        keep : nombre de sauvegardes à garder.
        client : client S3 ; None (défaut) pour s3_client().
        dest_dir : dossier où l'archive est créée le temps de l'envoi.

    Renvoie :
        {"uploaded": clé envoyée, "deleted": clés supprimées par la rotation}.

    Lève :
        BackupError : dossier introuvable, ou erreur S3 (identifiants, MinIO injoignable…).

    Exemple (faux stockage en mémoire, sans bucket au départ) :
        >>> import tempfile
        >>> work = Path(tempfile.mkdtemp())
        >>> (work / "config").mkdir()
        >>> _ = (work / "config" / "app.conf").write_text("port=8080\\n")
        >>> s3 = MemoryS3()
        >>> result = backup(work / "config", "cloudnova-backups", client=s3, dest_dir=work)
        >>> result["uploaded"].startswith("backups/backup-"), result["deleted"]
        (True, [])
        >>> metadata = s3.head_object(Bucket="cloudnova-backups", Key=result["uploaded"])["Metadata"]
        >>> len(metadata.get("sha256", ""))
        64
        >>> sorted(p.name for p in work.iterdir())
        ['config']
    """
    # Import ici : botocore est installé avec boto3, au lab 4.4
    from botocore.exceptions import BotoCoreError, ClientError

    # Vrai client S3, sauf si on en fournit un
    client = client or s3_client()
    # Archive locale ; BackupError si le dossier n'existe pas
    archive = make_archive(folder, dest_dir)
    # Bloc surveillé : les erreurs S3 deviennent des BackupError
    try:
        # Bucket créé si besoin, archive envoyée, anciennes sauvegardes supprimées
        ensure_bucket(client, bucket)
        key = upload(client, archive, bucket)
        deleted = rotate(client, bucket, keep)
    # BotoCoreError : identifiants absents, MinIO injoignable… ; ClientError : refus du service
    except (BotoCoreError, ClientError) as exc:
        raise BackupError(f"Échec S3 : {exc}") from exc
    # Exécuté dans tous les cas, succès ou erreur
    finally:
        # TODO 29 : supprimer l'archive locale, sans erreur si elle a déjà disparu.
        # Aide : même méthode de Path qu'au TODO 15 du lab 3.2.
        archive.unlink(missing_ok=True)
    # Bilan de la sauvegarde
    return {"uploaded": key, "deleted": deleted}


# ======================================================================================================
# Lab 4.5 — Webhook d'alerte et exporteur Prometheus
# ======================================================================================================

# Renvoie True si le message est parti ; une alerte ne doit jamais faire échouer le script qui l'envoie
def notify(text: str, webhook_url: str | None = None, timeout: float = 5.0) -> bool:
    """Envoie un message sur un webhook entrant (Teams, Slack, Mattermost) (lab 4.5).

    Le corps envoyé est {"text": text}. Sans URL, ou en cas d'échec, la fonction journalise et renvoie
    False, sans jamais lever d'exception.

    Paramètres :
        text : message à envoyer.
        webhook_url : adresse du webhook ; None (défaut) pour la lire dans OPS_WEBHOOK_URL.
        timeout : délai maximal de l'envoi, en secondes.

    Renvoie :
        True si le webhook a répondu par un succès, False sinon.

    Exemples (un petit serveur local joue le rôle du webhook et garde ce qu'il reçoit) :
        >>> received = []
        >>> class Hook(BaseHTTPRequestHandler):
        ...     def do_POST(self):
        ...         received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        ...         self.send_response(200)
        ...         self.end_headers()
        ...     def log_message(self, *args):
        ...         pass
        >>> hook = ThreadingHTTPServer(("127.0.0.1", 0), Hook)
        >>> threading.Thread(target=hook.serve_forever, daemon=True).start()
        >>> url = f"http://127.0.0.1:{hook.server_port}/hook"
        >>> notify("services KO", webhook_url=url)
        True
        >>> os.environ["OPS_WEBHOOK_URL"] = url
        >>> notify("lu dans l'environnement")
        True
        >>> received
        [{'text': 'services KO'}, {'text': "lu dans l'environnement"}]
        >>> del os.environ["OPS_WEBHOOK_URL"]
        >>> notify("personne pour le recevoir")
        False
        >>> hook.shutdown()
        >>> hook.server_close()
    """
    # TODO 30 : si webhook_url vaut None, lire l'adresse dans la variable d'environnement OPS_WEBHOOK_URL.
    # Aide : comme au TODO 1.
    url = webhook_url if webhook_url is not None else os.environ.get("OPS_WEBHOOK_URL")
    # Pas de webhook configuré : ce n'est pas une erreur, on le signale simplement
    if not url:
        log.info("Pas de OPS_WEBHOOK_URL : notification ignorée")
        return False
    # Bloc surveillé : un webhook en panne ne doit pas faire planter le script
    try:
        # TODO 31 : envoyer {"text": text} en JSON par une requête POST sur url, avec le timeout.
        # Aide : diapositive 59, partie A.
        response = requests.post(url, json={"text": text}, timeout=timeout)
        # ok vaut True pour un code 2xx ou 3xx
        return response.ok
    # Connexion impossible, délai dépassé… : un avertissement, et False
    except requests.RequestException as exc:
        log.warning("Notification impossible : %s", exc)
        return False


# Les jauges sont rangées dans un registre : un par exporteur, et un par exemple de doctest
def make_gauges(registry) -> tuple:
    """Crée les deux jauges de l'exporteur, étiquetées par nom de cible et port (lab 4.5).

    Paramètres :
        registry : registre prometheus_client (CollectorRegistry) où ranger les jauges.

    Renvoie :
        (up, latency) : opstoolkit_target_up et opstoolkit_target_latency_ms.
    """
    # Import ici : prometheus_client n'est installé qu'au lab 4.5
    from prometheus_client import Gauge

    # Jauge « la cible répond » : 1 ou 0, une valeur par couple d'étiquettes (name, port)
    up = Gauge("opstoolkit_target_up", "1 si le port répond, 0 sinon", ["name", "port"], registry=registry)
    # TODO 33 : seconde jauge, opstoolkit_target_latency_ms (temps de connexion TCP en millisecondes), avec
    #           les mêmes étiquettes et le même registre que up.
    # Aide : copiez la ligne de up, en changeant le nom et la description.
    latency = Gauge("opstoolkit_target_latency_ms", "Temps de connexion TCP en millisecondes", ["name", "port"], registry=registry)
    # Les deux jauges
    return up, latency


# results vient de check_targets() : une ligne par port testé
def update_metrics(up, latency, results: list[dict]) -> None:
    """Met à jour les deux jauges avec le résultat des tests de ports (lab 4.5).

    Exemple (sans réseau : deux résultats écrits à la main) :
        >>> from prometheus_client import CollectorRegistry, generate_latest
        >>> registry = CollectorRegistry()
        >>> up, latency = make_gauges(registry)
        >>> update_metrics(up, latency, [{"name": "web-dev", "port": 8081, "ok": True, "ms": 1},
        ...                              {"name": "cache-dev", "port": 6379, "ok": False, "ms": None}])
        >>> for line in generate_latest(registry).decode().splitlines():
        ...     if line.startswith("opstoolkit_"):
        ...         print(line)
        opstoolkit_target_up{name="web-dev",port="8081"} 1.0
        opstoolkit_target_up{name="cache-dev",port="6379"} 0.0
        opstoolkit_target_latency_ms{name="web-dev",port="8081"} 1.0
        opstoolkit_target_latency_ms{name="cache-dev",port="6379"} 0.0
    """
    # Une mise à jour par port testé
    for r in results:
        # Étiquettes de la cible ; Prometheus attend des textes
        labels = (r["name"], str(r["port"]))
        # TODO 34 : valeur de opstoolkit_target_up pour cette cible : 1 si le port répond, 0 sinon.
        # Aide : r["ok"] vaut True ou False ; une expression conditionnelle tient sur une ligne.
        up.labels(*labels).set(1 if r["ok"] else 0)
        # Latence en ms ; 0 quand le port ne répond pas (ms vaut None)
        latency.labels(*labels).set(r["ms"] or 0)


# Tourne jusqu'à Ctrl+C : Prometheus vient lire /metrics à intervalle régulier
def start_exporter(servers: list[dict], port: int = 9105, interval: int = 15,
                   addr: str = "127.0.0.1") -> None:
    """Expose opstoolkit_target_up et opstoolkit_target_latency_ms sur http://addr:port/metrics (lab 4.5).

    Les ports de servers sont testés toutes les interval secondes, jusqu'à l'arrêt du programme.

    Résultat attendu avec l'environnement dev du labo :
        opstoolkit_target_up{name="web-dev",port="8081"} 1.0
        opstoolkit_target_up{name="cache-dev",port="6379"} 1.0
        opstoolkit_target_latency_ms{name="web-dev",port="8081"} 1.0
        opstoolkit_target_latency_ms{name="cache-dev",port="6379"} 0.0
    """
    # Import ici : prometheus_client n'est installé qu'au lab 4.5
    # (noqa : start_http_server ne sert qu'une fois le TODO 35 fermé ; ruff --fix ne doit pas le retirer)
    from prometheus_client import CollectorRegistry, start_http_server  # noqa: F401

    # Registre propre à cet exporteur, et ses deux jauges
    registry = CollectorRegistry()
    up, latency = make_gauges(registry)
    # TODO 35 : démarrer le serveur HTTP qui publie le registre sur addr:port, page /metrics.
    # Aide : diapositive 59, partie B ; start_http_server accepte port, addr= et registry=.
    start_http_server(port, addr=addr, registry=registry)
    # Adresse à donner à Prometheus, ou à curl
    log.info("Exporteur sur http://%s:%d/metrics (Ctrl+C pour arrêter)", addr, port)
    # Mesure, pause, et ainsi de suite
    while True:
        # Tests de ports du socle, puis mise à jour des jauges
        update_metrics(up, latency, check_targets(servers))
        # Pause jusqu'à la mesure suivante
        time.sleep(interval)


# ======================================================================================================
# Ligne de commande : une fonction par sous-commande, puis l'analyseur et main()
# ======================================================================================================

# Chaque sous-commande reçoit les arguments lus par argparse et renvoie un code retour
def cmd_api(args: argparse.Namespace) -> int:
    """Sous-commande « api » : composants dégradés de l'API de statut, et incidents (lab 4.1).

    Paramètres :
        args : arguments lus par argparse ; args.url est l'adresse de l'API, args.create_incidents vaut
            True avec --create-incidents.

    Renvoie :
        0 si tout est opérationnel, 1 si au moins un composant est dégradé. Erreur d'appel : 2, via main().
    """
    # Client de l'API ; StatusApiError si le token manque
    client = StatusClient(args.url)
    # Composants dégradés ou en panne
    degraded = client.degraded()
    # Une ligne par composant dégradé
    for c in degraded:
        print(f"[DÉGRADÉ] {c['name']} : {c['status']}")
        # Avec --create-incidents : un incident par composant dégradé
        if args.create_incidents:
            incident = client.create_incident(c["name"], f"{c['name']} en {c['status']}", "major")
            print(f"  incident n°{incident['id']} créé")
    # Rien à signaler : on le dit
    if not degraded:
        print("Tous les composants sont opérationnels")
    # TODO 11 : code retour 1 si au moins un composant est dégradé, 0 sinon.
    # Aide : une liste vide est « fausse » ; convention des codes retour en tête de fichier.
    # Réponse : une liste vide est « fausse », une liste non vide « vraie » : 1 dès qu'un composant est dégradé.
    return 1 if degraded else 0


# Même signature pour toutes les sous-commandes
def cmd_serve(args: argparse.Namespace) -> int:
    """Sous-commande « serve » : lance l'API d'OpsToolkit avec uvicorn, jusqu'à Ctrl+C (lab 4.2).

    Paramètres :
        args : arguments lus par argparse ; args.host, args.port et args.inventory.

    Renvoie :
        0 à l'arrêt du serveur.
    """
    # Import ici : uvicorn n'est installé qu'au lab 4.2
    # (noqa : uvicorn ne sert qu'une fois le TODO 16 fermé ; ruff --fix ne doit pas le retirer)
    import uvicorn  # noqa: F401

    # Documentation interactive de l'API
    log.info("Documentation : http://%s:%d/docs", args.host, args.port)
    # TODO 16 : démarrer le serveur uvicorn avec l'application create_app(args.inventory), sur l'hôte et le
    #           port demandés.
    # Aide : diapositive 55 (uvicorn en ligne de commande) ; depuis Python : uvicorn.run(app, host=, port=).
    # Réponse : uvicorn.run() lance le serveur web et bloque jusqu'à Ctrl+C ; create_app() fabrique l'API.
    uvicorn.run(create_app(args.inventory), host=args.host, port=args.port)
    # Code 0 : serveur arrêté normalement
    return 0


# Même signature pour toutes les sous-commandes
def cmd_docker(args: argparse.Namespace) -> int:
    """Sous-commande « docker » : état des conteneurs du labo, redémarrage, journal (lab 4.3).

    Paramètres :
        args : arguments lus par argparse ; args.restart vaut True avec --restart, args.logs est le nom
            d'un conteneur (None sans l'option).

    Renvoie :
        0 si tous les conteneurs du labo tournent, 1 sinon ; 2 si Docker est injoignable ou si le
        conteneur demandé n'existe pas.
    """
    # Import ici : le SDK Docker n'est installé qu'au lab 4.3 ; il fournit aussi ses exceptions
    import docker

    # Bloc surveillé : démon arrêté, droits insuffisants sur le socket, conteneur inconnu
    try:
        # Bonus : journal d'un conteneur, puis fin
        if args.logs:
            print(container_logs(args.logs))
            return 0
        # Avec --restart : relancer les conteneurs arrêtés
        if args.restart:
            for name in restart_stopped():
                print(f"Redémarré : {name}")
        # État des conteneurs, après un éventuel redémarrage
        containers = lab_containers()
    # Conteneur demandé par --logs inexistant
    except docker.errors.NotFound:
        log.error("Conteneur introuvable : %s", args.logs)
        return 2
    # Toute autre erreur du SDK : le plus souvent, Docker n'est pas démarré
    except docker.errors.DockerException as exc:
        log.error("Docker injoignable : %s", exc)
        return 2
    # Aucun conteneur du labo : il n'a jamais été créé
    if not containers:
        log.warning("Aucun conteneur lab-… : cd ~/lab && docker compose up -d")
        return 1
    # Une ligne par conteneur : nom, statut, image
    for c in containers:
        print(f"{c['name']:<16}{c['status']:<10}{c['image']}")
    # 1 si un conteneur du labo ne tourne pas
    return 1 if any(c["status"] != "running" for c in containers) else 0


# Même signature pour toutes les sous-commandes
def cmd_backup(args: argparse.Namespace) -> int:
    """Sous-commande « backup » : sauvegarde d'un dossier vers S3 / MinIO, avec rotation (lab 4.4).

    Paramètres :
        args : arguments lus par argparse ; args.folder, args.bucket et args.keep.

    Renvoie :
        0. Dossier introuvable ou erreur S3 : 2, via main().
    """
    # Archive, envoi, rotation
    result = backup(args.folder, args.bucket, args.keep)
    # Clé de la sauvegarde envoyée
    print(f"Envoyé : {result['uploaded']}")
    # Une ligne par sauvegarde supprimée par la rotation
    for key in result["deleted"]:
        print(f"Rotation : {key} supprimé")
    # Code 0 : sauvegarde réussie
    return 0


# Même signature pour toutes les sous-commandes
def cmd_health(args: argparse.Namespace) -> int:
    """Sous-commande « health » : test des ports de l'inventaire, avec alerte facultative (labs 3.3 et 4.5).

    Paramètres :
        args : arguments lus par argparse ; args.env, args.timeout, et args.notify qui vaut True avec
            --notify.

    Renvoie :
        0 si tous les ports répondent, 1 si au moins un est KO. Inventaire invalide : 2, via main().
    """
    # Un résultat par port de l'environnement demandé
    results = check_targets(servers_of(load_inventory(args.inventory), args.env), timeout=args.timeout)
    # Une ligne par port, comme au lab 3.3
    for r in results:
        ms = f"{r['ms']} ms" if r["ms"] is not None else "-"
        print(f"[{'OK' if r['ok'] else 'KO'}] {r['name']:<13}{r['host']}:{r['port']:<6} {ms}")
    # Cibles en échec, sous la forme nom:port
    failed = [f"{r['name']}:{r['port']}" for r in results if not r["ok"]]
    # TODO 32 : condition vraie si au moins un port est KO ET si l'option --notify est présente.
    # Aide : une liste non vide est « vraie » ; args.notify vaut True seulement avec --notify.
    if failed and args.notify:
        # Une seule alerte, qui liste toutes les cibles KO
        notify("OpsToolkit : services KO -> " + ", ".join(failed))
    # 1 si au moins un port est KO
    return 1 if failed else 0


# Même signature pour toutes les sous-commandes
def cmd_exporter(args: argparse.Namespace) -> int:
    """Sous-commande « exporter » : exporteur Prometheus des ports de l'inventaire, jusqu'à Ctrl+C (lab 4.5).

    Paramètres :
        args : arguments lus par argparse ; args.env, args.port et args.interval.

    Renvoie :
        0 à l'arrêt par Ctrl+C. Inventaire invalide : 2, via main().
    """
    # Serveurs de l'environnement demandé
    servers = servers_of(load_inventory(args.inventory), args.env)
    # Ctrl+C lève KeyboardInterrupt : c'est la façon normale d'arrêter l'exporteur
    try:
        start_exporter(servers, port=args.port, interval=args.interval)
    except KeyboardInterrupt:
        log.info("Exporteur arrêté")
    # Code 0 : arrêt normal
    return 0


# Renvoie l'analyseur de la ligne de commande, prêt à l'emploi
def build_parser() -> argparse.ArgumentParser:
    """Construit l'analyseur de la ligne de commande : options générales et sous-commandes.

    Chaque sous-commande enregistre, avec set_defaults(func=…), la fonction qui la traite.

    Renvoie :
        L'analyseur argparse.
    """
    # Analyseur principal ; prog fixe le nom affiché dans l'aide
    parser = argparse.ArgumentParser(prog="lab4", description="Labs du jour 4 : API, conteneurs et cloud")
    # Option générale : messages de niveau DEBUG
    parser.add_argument("-v", "--verbose", action="store_true", help="logs détaillés (DEBUG)")
    # Option générale : chemin de l'inventaire YAML, utilisé par serve, health et exporter
    parser.add_argument("-i", "--inventory", default="data/inventory.yaml", help="fichier d'inventaire YAML")
    # Groupe des sous-commandes ; required=True oblige à en choisir une
    sub = parser.add_subparsers(dest="command_name", required=True)

    # Lab 4.1 : « api [--url URL] [--create-incidents] »
    p = sub.add_parser("api", help="composants dégradés de l'API de statut (lab 4.1)")
    # Adresse de l'API ; le token, lui, ne passe jamais en argument
    p.add_argument("--url", default="http://127.0.0.1:8000", help="adresse de l'API (défaut : labo)")
    # Drapeau : créer un incident par composant dégradé
    p.add_argument("--create-incidents", action="store_true", help="créer un incident par composant dégradé")
    p.set_defaults(func=cmd_api)

    # Lab 4.2 : « serve [--host H] [--port P] »
    p = sub.add_parser("serve", help="lancer l'API d'OpsToolkit (lab 4.2)")
    # 127.0.0.1 : accessible depuis ce poste seulement ; 0.0.0.0 pour la démo croisée avec un voisin
    p.add_argument("--host", default="127.0.0.1", help="adresse d'écoute (défaut : 127.0.0.1)")
    # Port d'écoute, 8090 comme dans le cours
    p.add_argument("--port", type=int, default=8090, help="port d'écoute (défaut : 8090)")
    p.set_defaults(func=cmd_serve)

    # Lab 4.3 : « docker [--restart] [--logs NOM] »
    p = sub.add_parser("docker", help="conteneurs du labo avec le SDK Docker (lab 4.3)")
    # Drapeau : relancer les conteneurs arrêtés
    p.add_argument("--restart", action="store_true", help="redémarrer les conteneurs lab- arrêtés")
    # Bonus : journal d'un conteneur
    p.add_argument("--logs", metavar="NOM", help="afficher les 5 dernières lignes du journal de NOM")
    p.set_defaults(func=cmd_docker)

    # Lab 4.4 : « backup DOSSIER [--bucket B] [--keep N] »
    p = sub.add_parser("backup", help="sauvegarder un dossier vers S3 / MinIO (lab 4.4)")
    # Argument obligatoire : le dossier à sauvegarder
    p.add_argument("folder", help="dossier à sauvegarder")
    # Bucket de destination
    p.add_argument("--bucket", default="cloudnova-backups", help="bucket (défaut : cloudnova-backups)")
    # Nombre de sauvegardes gardées
    p.add_argument("--keep", type=int, default=5, help="sauvegardes gardées (défaut : 5)")
    p.set_defaults(func=cmd_backup)

    # Lab 4.5 : « health [--env ENV] [--timeout S] [--notify] »
    p = sub.add_parser("health", help="tester les ports de l'inventaire, et alerter (labs 3.3 et 4.5)")
    # Environnement à tester ; sans l'option, tous les environnements
    p.add_argument("--env", help="dev, recette ou prod (défaut : tous)")
    # Délai de chaque connexion, en secondes
    p.add_argument("--timeout", type=float, default=2.0, help="timeout de chaque test en s (défaut : 2)")
    # Drapeau : alerte sur le webhook si un port est KO
    p.add_argument("--notify", action="store_true", help="alerter via OPS_WEBHOOK_URL si un port est KO")
    p.set_defaults(func=cmd_health)

    # Lab 4.5 : « exporter [--env ENV] [--port P] [--interval S] »
    p = sub.add_parser("exporter", help="exporteur Prometheus des ports de l'inventaire (lab 4.5)")
    # Environnement exporté ; sans l'option, tous les environnements
    p.add_argument("--env", help="dev, recette ou prod (défaut : tous)")
    # Port de la page /metrics
    p.add_argument("--port", type=int, default=9105, help="port de /metrics (défaut : 9105)")
    # Intervalle entre deux mesures
    p.add_argument("--interval", type=int, default=15, help="secondes entre deux mesures (défaut : 15)")
    p.set_defaults(func=cmd_exporter)

    # Renvoi de l'analyseur complet
    return parser


# argv vaut None par défaut : argparse lit alors la vraie ligne de commande
def main(argv: list[str] | None = None) -> int:
    """Point d'entrée : lit la ligne de commande, lance la sous-commande, gère les erreurs prévues.

    Paramètres :
        argv : arguments de la ligne de commande ; None (défaut) lit sys.argv.

    Renvoie :
        Le code retour de la sous-commande, ou 2 pour une erreur d'inventaire, d'API, de sauvegarde, ou
        une bibliothèque pas encore installée.
    """
    # Lecture des arguments ; une option inconnue affiche l'usage et quitte avec le code 2
    args = build_parser().parse_args(argv)
    # Niveau DEBUG avec -v, INFO sinon ; format « NIVEAU message » ; les logs vont sur stderr
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")
    # Bibliothèques bavardes en INFO ou DEBUG : on ne garde que leurs avertissements
    for name in ("urllib3", "botocore", "boto3", "docker"):
        logging.getLogger(name).setLevel(logging.WARNING)
    # Exécution surveillée : les erreurs prévues deviennent un message clair et le code 2
    try:
        # Appel de la fonction enregistrée par la sous-commande choisie
        return args.func(args)
    # Inventaire invalide (jour 2), erreur d'appel à l'API (lab 4.1), sauvegarde impossible (lab 4.4)
    except (InventoryError, StatusApiError, BackupError) as exc:
        log.error("%s", exc)
        return 2
    # Bibliothèque du jour pas encore installée : on dit laquelle
    except ModuleNotFoundError as exc:
        log.error("Bibliothèque absente : %s (voir « Installation » en tête de lab4.py)", exc.name)
        return 2


# Condition vraie seulement quand le fichier est lancé directement, pas quand il est importé
if __name__ == "__main__":
    # Lance main() et transmet son code retour au shell, visible avec « echo $? »
    sys.exit(main())

