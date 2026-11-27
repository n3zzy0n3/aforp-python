"""Client de l'API de statut de CloudNova (lab 4.1).

FakeStatusAPI imite lab-status-api : elle sert aux exemples (python -m doctest), sans le labo Docker.
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import requests

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
        self.token = token if token is not None else os.environ.get("STATUS_API_TOKEN")
        # Sans token, inutile d'aller plus loin : le message dit quoi faire, sans afficher de secret
        if not self.token:
            raise StatusApiError("Variable STATUS_API_TOKEN absente : export STATUS_API_TOKEN=...")
        # Délai de chaque appel
        self.timeout = timeout
        # Une session réutilise la connexion et porte des en-têtes communs à toutes les requêtes
        self.session = requests.Session()
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
            response = self.session.request(method, self.base_url + path, timeout=self.timeout, **kwargs)
        # Délai dépassé (à placer avant ConnectionError : un délai de connexion est les deux à la fois)
        except requests.Timeout as exc:
            raise StatusApiError(f"Pas de réponse en {self.timeout} s sur {path}") from exc
        # Rien n'écoute à cette adresse : le plus souvent, le conteneur est arrêté
        except requests.ConnectionError as exc:
            raise StatusApiError(f"API injoignable ({self.base_url}) : conteneur démarré ?") from exc
        # Message lisible pour chaque erreur du client que l'on sait expliquer
        messages = {401: "token manquant", 403: "token refusé", 404: "ressource introuvable"}
        if response.status_code in messages:
            # Par exemple « 403 sur /components : token refusé »
            raise StatusApiError(f"{response.status_code} sur {path} : {messages[response.status_code]}")
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
            data = self._request("GET", "/components", params={"page": page, "per_page": per_page}).json()
            items.extend(data["items"])
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
        return self._request("POST", "/incidents", json=payload).json()
