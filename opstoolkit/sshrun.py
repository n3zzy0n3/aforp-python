"""Exécution de commandes à distance en SSH avec paramiko (lab 3.5)."""
import os
from concurrent.futures import ThreadPoolExecutor


# Renvoie un dictionnaire : adresse, réussite, code retour distant, sorties
def run_remote(host: str, command: str, port: int = 22, user: str = "ops",
               password: str | None = None, timeout: float = 5.0) -> dict:
    """Exécute une commande sur un serveur en SSH ; renvoie son code retour et ses sorties (lab 3.5).

    Le mot de passe n'est jamais écrit dans le code : sans paramètre password, il est lu dans la
    variable d'environnement OPS_SSH_PASSWORD. Aucune erreur ne remonte : un échec donne ok=False.

    Paramètres :
        host : adresse du serveur, par exemple « 127.0.0.1 ».
        command : commande à exécuter, par exemple « hostname && uptime -p ».
        port : port SSH ; 2221 pour app01 et 2222 pour app02 au labo.
        user : compte de connexion, « ops » au labo.
        password : mot de passe ; None (défaut) pour le lire dans OPS_SSH_PASSWORD.
        timeout : délai maximal de connexion et d'exécution, en secondes.

    Renvoie :
        {"host": "hôte:port", "ok": True si le code retour distant vaut 0, "code": code retour distant
        (None sans connexion), "stdout": sortie standard, "stderr": sortie d'erreur ou message d'erreur}.
    """
    # Importé ici et non en tête de fichier : paramiko n'est installé qu'au lab 3.5,
    # et les labs 3.1 à 3.4 doivent fonctionner sans lui
    import paramiko

    if password is None:
        password = os.environ.get("OPS_SSH_PASSWORD")
    # Client SSH ; par défaut, il refuse tout serveur absent de known_hosts (RejectPolicy)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # Bloc surveillé : erreurs de connexion, d'authentification, de clé d'hôte ou de délai
    try:
        # Connexion par mot de passe ; allow_agent et look_for_keys à False : aucune clé locale essayée
        client.connect(host, port=port, username=user, password=password, timeout=timeout,
                       allow_agent=False, look_for_keys=False)
        _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        code = stdout.channel.recv_exit_status()
        # Résultat de la commande : ok seulement si le code retour distant vaut 0
        return {"host": f"{host}:{port}", "ok": code == 0, "code": code, "stdout": out, "stderr": err}
    # SSHException : authentification refusée, clé d'hôte inconnue… ; OSError : port fermé, délai dépassé
    except (paramiko.SSHException, OSError) as exc:
        # Pas de code retour : la commande n'a pas tourné ; le message d'erreur va dans stderr
        return {"host": f"{host}:{port}", "ok": False, "code": None, "stdout": "", "stderr": str(exc)}
    # Exécuté dans tous les cas : après le return du try comme après celui de l'except
    finally:
        client.close()


# Renvoie un résultat par serveur SSH, dans l'ordre de la liste
def run_on_servers(servers: list[dict], command: str, workers: int = 5) -> list[dict]:
    """Exécute la même commande, en parallèle, sur tous les serveurs SSH de la liste (lab 3.5).

    Paramètres :
        servers : serveurs de l'inventaire ; seuls ceux qui ont une clé « ssh_port » sont concernés.
        command : commande à exécuter sur chaque serveur.
        workers : nombre de connexions SSH simultanées.

    Renvoie :
        Un résultat run_remote() par serveur SSH, précédé de son nom : {"name": …, "host": …, …}.

    Exemple (un serveur sans ssh_port n'est pas contacté) :
        >>> run_on_servers([{"name": "web-dev", "host": "127.0.0.1", "ports": [8081]}], "hostname")
        []
    """
    targets: list[dict] = [s for s in servers if "ssh_port" in s]

    # Fonction locale : le travail d'un thread, pour un serveur ; elle voit la variable command
    def one(server: dict) -> dict:
        """Exécute command sur un serveur et place son nom en tête du résultat de run_remote().

        Paramètres :
            server : un serveur de l'inventaire, avec « name », « host » et « ssh_port ».

        Renvoie :
            {"name": nom du serveur, puis toutes les clés du résultat de run_remote()}.
        """
        # ** recopie toutes les clés du résultat de run_remote à la suite de « name »
        return {"name": server["name"], **run_remote(server["host"], command, port=server["ssh_port"])}

    # Une connexion SSH par thread ; map garde l'ordre des serveurs
    with ThreadPoolExecutor(max_workers=workers) as pool:
        # list() récupère tous les résultats avant la sortie du bloc
        return list(pool.map(one, targets))
