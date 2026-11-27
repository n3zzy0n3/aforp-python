"""Docker, webhook d'alerte et exporteur Prometheus (labs 4.3 et 4.5, bonus)."""
import json  # noqa: F401  (utilisé par les exemples de notify())
import logging
import os
import threading  # noqa: F401  (utilisé par les exemples de notify())
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: F401  (exemples de notify())

import requests

log = logging.getLogger(__name__)


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
    containers = client.containers.list(all=True)
    # Conteneurs retenus
    result = []
    # Parcours de tous les conteneurs du poste
    for c in containers:
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
    for c in client.containers.list(all=True, filters={"status": "exited"}):
        # Seulement les conteneurs du labo : jamais ceux des autres projets du poste
        if c.name.startswith(prefix):
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
    return client.containers.get(name).logs(tail=tail).decode(errors="replace")


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
    url = webhook_url if webhook_url is not None else os.environ.get("OPS_WEBHOOK_URL")
    # Pas de webhook configuré : ce n'est pas une erreur, on le signale simplement
    if not url:
        log.info("Pas de OPS_WEBHOOK_URL : notification ignorée")
        return False
    # Bloc surveillé : un webhook en panne ne doit pas faire planter le script
    try:
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
    latency = Gauge("opstoolkit_target_latency_ms", "Temps de connexion TCP en millisecondes",
                    ["name", "port"], registry=registry)
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
    from prometheus_client import CollectorRegistry, start_http_server

    # Tests de ports du package (jour 3)
    from .health import check_targets

    # Registre propre à cet exporteur, et ses deux jauges
    registry = CollectorRegistry()
    up, latency = make_gauges(registry)
    start_http_server(port, addr=addr, registry=registry)
    # Adresse à donner à Prometheus, ou à curl
    log.info("Exporteur sur http://%s:%d/metrics (Ctrl+C pour arrêter)", addr, port)
    # Mesure, pause, et ainsi de suite
    while True:
        # Tests de ports du socle, puis mise à jour des jauges
        update_metrics(up, latency, check_targets(servers))
        # Pause jusqu'à la mesure suivante
        time.sleep(interval)
