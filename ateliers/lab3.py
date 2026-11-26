"""Labs du jour 3 — Système et réseau : code à trous.

Ce fichier contient toutes les fonctions des labs 3.1 à 3.5 et une ligne de commande pour les lancer.
L'essentiel est écrit : vous fermez les trous, dans l'ordre de leurs numéros.

Reconnaître un trou
    Chaque trou est annoncé par un commentaire « TODO n » qui décrit ce qu'il faut obtenir, suivi d'une
    « Aide » qui dit où chercher, sans donner la réponse. La ligne à remplacer se termine par le repère
    « # <- TODO n ». Elle contient une valeur provisoire (False, 0, [], pass…) qui laisse le fichier
    tourner, mais donne un résultat faux ou vide. Remplacez toute cette ligne par votre code (une ou
    plusieurs lignes), en gardant son indentation, et supprimez le repère.

Où chercher
    Les diapositives 38 à 45 du cours, et doc-3.pdf : une partie par notion, avec un exemple pris dans
    un autre contexte que le lab. À vous de transposer.

Règles du jour, vérifiées au livrable n°2
    Aucun shell=True ni os.system ; un timeout sur chaque appel système ou réseau ; aucun mot de passe
    dans le code ; aucune suppression sans --force.

Installation, sous Linux ou WSL (uptime -p et ps --sort n'existent que sous Linux)
    Dans ~/aforp-python, venv activé.
    data/inventory.yaml est là depuis le lab 2.3 ; sinon : cp ~/lab/data/inventory.yaml data/
    Labo Docker démarré : cd ~/lab && docker compose up -d && ./scripts/check_lab.sh
    Au lab 3.5 seulement : pip install paramiko && pip freeze > requirements.txt
    Puis copier lab3.py à la racine du projet, à côté du dossier data/.

Lab  Trous          Commandes de contrôle
3.1  TODO 1 à 12    python lab3.py sysinfo | python -m json.tool
                    python lab3.py sysinfo --alert 1; echo "code=$?"               (code=1)
3.2  TODO 13 à 16   mkdir -p /tmp/vieux-logs && cd /tmp/vieux-logs
                    touch -d "10 days ago" a.log b.log && touch c.log && cd -
                    python lab3.py sysinfo --clean /tmp/vieux-logs                 (2 fichiers, dry-run)
                    python lab3.py sysinfo --clean /tmp/vieux-logs --force         (ls : c.log seul)
3.3  TODO 17 à 22   docker stop lab-db
                    python lab3.py health --env prod; echo "code=$?"               (db-prod KO, code=1)
                    docker start lab-db, puis relancer health                      (code=0)
3.4  TODO 23 à 25   python lab3.py bench http://127.0.0.1:8000/slow                (8.0 s, puis 2.0 s)
3.5  TODO 26 à 31   export OPS_SSH_PASSWORD=ops-lab
                    python lab3.py ssh "hostname && uptime -p"                     (app01, app02, code=0)
                    unset OPS_SSH_PASSWORD; python lab3.py ssh hostname; echo "code=$?"    (code=2)

Vérifier les fonctions avec les exemples des docstrings (sans le labo Docker)
    python -m doctest lab3.py
    Aucun affichage : tous les exemples passent. Sinon, doctest montre l'exemple en échec,
    le résultat attendu et le résultat obtenu.

Codes retour : 0 = tout va bien, 1 = une cible est KO (disque en alerte, port ou serveur en échec),
2 = erreur d'usage ou de configuration (convention d'OpsToolkit).
"""
# argparse : lecture des sous-commandes et des options de la ligne de commande
import argparse
# json : affichage de l'état du poste en JSON (lab 3.1)
import json
# logging : messages de suivi sur la sortie d'erreur, distincts du résultat affiché par print
import logging
# os : variables d'environnement, pour le mot de passe SSH (lab 3.5)
# (noqa : tant que les trous sont ouverts, ce module ne sert pas encore ; ruff --fix ne doit pas le retirer)
import os  # noqa: F401
# platform : nom et version du système, version de Python (lab 3.1)
import platform
# shutil : informations sur les disques, sans lancer de commande (lab 3.1) ; noqa : même raison que pour os
import shutil  # noqa: F401
# socket : nom d'hôte (lab 3.1) et connexions TCP (lab 3.3) ; noqa : même raison que pour os
import socket  # noqa: F401
# subprocess : lancer une commande système, sans shell (lab 3.1)
import subprocess
# sys : sys.exit transmet le code retour au shell
import sys
# time : âge des fichiers (lab 3.2) et mesure des durées (labs 3.3 et 3.4)
import time
# ThreadPoolExecutor : groupe de threads, pour faire attendre plusieurs tests en même temps (labs 3.4 et 3.5)
from concurrent.futures import ThreadPoolExecutor
# Path : chemins de fichiers sous forme d'objets (lab 3.2)
from pathlib import Path

# requests : requêtes HTTP (lab 3.3), installé depuis le jour 1
import requests
# yaml, fourni par le paquet PyYAML : lecture de l'inventaire (jour 2)
import yaml

# Journal propre à ce fichier ; main() règle son niveau et son format
log = logging.getLogger("lab3")
# Champs obligatoires de chaque serveur de l'inventaire YAML (jour 2)
REQUIRED_KEYS = {"name", "host", "role", "ports"}


# ======================================================================================================
# Socle du jour 2 (lab 2.3) : lecture de l'inventaire. Déjà complet, rien à modifier.
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


# ======================================================================================================
# Lab 3.1 — subprocess : état du poste en JSON
# ======================================================================================================

# cmd est une liste de textes ; la fonction renvoie un couple (code retour, sortie standard)
def run(cmd: list[str], timeout: float = 10) -> tuple[int, str]:
    """Exécute une commande système SANS shell ; renvoie son code retour et sa sortie standard (lab 3.1).

    La fonction ne lève jamais d'exception quand la commande échoue : elle renvoie un code, comme le
    ferait le shell. Un code non nul est journalisé, avec le message d'erreur de la commande.

    Paramètres :
        cmd : la commande sous forme de liste, un élément par argument, par exemple ["uptime", "-p"].
        timeout : durée maximale en secondes ; au-delà, la commande est arrêtée.

    Renvoie :
        (code retour, sortie standard en texte). Programme introuvable : (127, "").
        Délai dépassé : (124, "").

    Exemples :
        >>> run([sys.executable, "-c", "print('bonjour')"])
        (0, 'bonjour\\n')
        >>> run(["commande-inexistante-aforp"])
        (127, '')
        >>> run([sys.executable, "-c", "import time; time.sleep(5)"], timeout=1)
        (124, '')
    """
    # Bloc surveillé : les deux échecs prévus deviennent un code retour, pas une trace Python
    try:
        # TODO 1 : lancer cmd sans shell ; récupérer stdout et stderr sous forme de texte ; arrêter la
        #          commande au-delà de timeout ; ne PAS lever d'exception si le code retour n'est pas 0.
        # Aide : diapositive 38, colonne « À faire », et doc-3.pdf, partie 1 : quatre paramètres nommés.
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    # Le programme n'existe pas sur ce poste (macOS sans « uptime -p », image minimale…)
    except FileNotFoundError:
        # TODO 2 : renvoyer le code que le shell donne à « command not found », et une sortie vide.
        # Aide : doc-3.pdf, partie 1, tableau « Une commande peut échouer de trois façons ».
        return 127, ""
    # Le programme n'a pas répondu à temps : subprocess l'a déjà arrêté
    except subprocess.TimeoutExpired:
        # TODO 3 : renvoyer le code de la commande Linux « timeout » quand le délai est dépassé, et "".
        # Aide : même tableau qu'au TODO 2, ou essayez « timeout 1 sleep 5; echo $? » dans un terminal.
        return 124, ""
    # La commande a tourné mais signale un échec : on le journalise, avec son message d'erreur
    if result.returncode != 0:
        # cmd[0] est le nom du programme ; strip() retire le saut de ligne final de stderr
        log.warning("%s a échoué (code %d) : %s", cmd[0], result.returncode, result.stderr.strip())
    # Code retour et sortie standard, que la commande ait réussi ou non
    return result.returncode, result.stdout


# path est un point de montage ; alert_pct le seuil d'alerte en pourcentage
def disk_usage(path: str = "/", alert_pct: int = 80) -> dict:
    """Mesure l'occupation d'un disque, sans lancer df (lab 3.1).

    Paramètres :
        path : point de montage à mesurer, « / » par défaut.
        alert_pct : seuil d'alerte en pourcentage ; l'alerte est levée dès que l'occupation l'atteint.

    Renvoie :
        {"path": path, "total_gb": taille en Go (10**9 octets) arrondie à 0,1,
        "used_pct": pourcentage utilisé arrondi à 0,1, "alert": True si used_pct >= alert_pct}.

    Exemples :
        >>> d = disk_usage("/", alert_pct=0)
        >>> sorted(d)
        ['alert', 'path', 'total_gb', 'used_pct']
        >>> d["total_gb"] > 0 and 0 < d["used_pct"] < 100 and d["alert"]
        True
        >>> disk_usage("/", alert_pct=101)["alert"]
        False
    """
    # TODO 4 : taille totale et espace utilisé du disque path, en octets, SANS lancer de commande.
    # Aide : doc-3.pdf, partie 2, tableau « Information / Python », ligne « Espace disque ».
    total, used, _free = shutil.disk_usage(path)
    # TODO 5 : pourcentage d'espace utilisé, arrondi à 1 décimale.
    # Aide : une règle de trois avec les deux valeurs du TODO 4, puis un arrondi.
    pct = round(used / total * 100, 1)
    # Dictionnaire sérialisable en JSON
    return {
        # Point de montage mesuré
        "path": path,
        # Taille totale en Go : 1 Go = 10**9 octets, comme df -H
        "total_gb": round(total / 1e9, 1),
        # Pourcentage calculé au TODO 5
        "used_pct": pct,
        # TODO 6 : True si le pourcentage atteint ou dépasse le seuil, False sinon.
        # Aide : pas besoin de if : une comparaison vaut déjà True ou False.
        "alert": pct >= alert_pct,
    }


# n est le nombre de processus voulus ; la fonction renvoie une liste de dictionnaires
def top_memory(n: int = 5) -> list[dict]:
    """Liste les n processus qui occupent le plus de mémoire, avec ps (lab 3.1, Linux uniquement).

    Paramètres :
        n : nombre de processus à garder.

    Renvoie :
        Une liste de dictionnaires {"pid": int, "command": str, "mem_pct": float}, du plus gourmand
        au moins gourmand. Liste vide si ps échoue ou n'existe pas (macOS, Windows).

    Résultat attendu (valeurs propres à chaque poste) :
        [{"pid": 2412, "command": "code", "mem_pct": 6.1}, ...]
    """
    # TODO 7 : lancer ps avec run() pour obtenir, pour TOUS les processus, trois colonnes dans cet
    #          ordre : pid, %mem, comm ; les processus étant triés par mémoire décroissante.
    # Aide : man ps (options -e, -o et --sort) ; dans la liste, un élément par argument, sans espace.
    code, out = run(["ps", "-eo", "pid,%mem,comm", "--sort=-%mem"])
    # ps a échoué ou n'existe pas : pas de classement, mais pas de plantage non plus
    if code != 0:
        # Liste vide : collect() l'écrira telle quelle dans le JSON
        return []
    # Liste des processus retenus
    procs = []
    # TODO 8 : parcourir les n premières lignes de résultats, SANS la ligne d'en-tête de ps.
    # Aide : la sortie est un seul texte : découpez-la en lignes, puis ne gardez que la tranche utile.
    for line in out.splitlines()[1:n + 1]:
        # Découpage en 3 morceaux au plus : comm vient en dernier, car un nom peut contenir des espaces
        pid, mem, comm = line.split(None, 2)
        # TODO 9 : ajouter ce processus, avec des NOMBRES pour pid et mem_pct (le JSON attend des nombres).
        # Aide : split() ne renvoie que des textes ; quel type pour un numéro, quel type pour un pourcentage ?
        procs.append({"pid": int(pid), "command": comm, "mem_pct": float(mem)})
    # Du plus gourmand au moins gourmand, grâce au tri fait par ps
    return procs


# alert_pct est transmis à disk_usage ; la fonction renvoie un dictionnaire prêt pour json.dumps
def collect(alert_pct: int = 80) -> dict:
    """Rassemble l'état du poste dans un dictionnaire sérialisable en JSON (lab 3.1).

    Paramètres :
        alert_pct : seuil d'alerte disque en pourcentage, transmis à disk_usage().

    Renvoie :
        {"hostname", "system", "python", "uptime", "disk", "top_memory"}. uptime vaut None si la
        commande « uptime -p » échoue ou n'existe pas.

    Exemples :
        >>> info = collect()
        >>> sorted(info)
        ['disk', 'hostname', 'python', 'system', 'top_memory', 'uptime']
        >>> info["hostname"] == platform.node()
        True
    """
    # TODO 10 : temps de fonctionnement du poste, donné par la commande « uptime -p » lancée avec run().
    # Aide : run() renvoie déjà un couple (code, sortie) : un seul appel suffit.
    code, uptime = run(["uptime", "-p"])
    # Dictionnaire de l'état du poste ; json.dumps le convertira tel quel
    return {
        # TODO 11 : nom d'hôte du poste, sans lancer la commande hostname.
        # Aide : doc-3.pdf, partie 2 ; c'est le module qui sert aussi aux connexions TCP du lab 3.3.
        "hostname": socket.gethostname(),
        # Système et version du noyau, par exemple « Linux 6.8.0-49-generic »
        "system": f"{platform.system()} {platform.release()}",
        # Version de Python qui exécute ce script
        "python": platform.python_version(),
        # Sortie d'uptime sans le saut de ligne final ; None si la commande a échoué
        "uptime": uptime.strip() if code == 0 else None,
        # Occupation du disque racine, avec le seuil d'alerte demandé
        "disk": disk_usage("/", alert_pct),
        # Les 5 processus les plus gourmands en mémoire
        "top_memory": top_memory(),
    }


# ======================================================================================================
# Lab 3.2 — Nettoyage de vieux logs en dry-run
# ======================================================================================================

# dry_run vaut True par défaut : rien n'est supprimé sans une demande explicite
def clean_old_files(folder: str | Path, pattern: str = "*.log", days: int = 7,
                    dry_run: bool = True) -> list[Path]:
    """Liste, et en mode réel supprime, les fichiers plus vieux que `days` jours (lab 3.2).

    Seuls les fichiers du dossier lui-même sont concernés, pas ceux des sous-dossiers. Chaque fichier
    est journalisé : « [dry-run] supprimerait … » en simulation, « supprimé … » en mode réel.

    Paramètres :
        folder : dossier à nettoyer.
        pattern : motif des fichiers concernés, « *.log » par défaut.
        days : âge minimal en jours, d'après la date de dernière modification.
        dry_run : True (défaut) pour simuler, False pour supprimer réellement.

    Renvoie :
        La liste triée des fichiers concernés, supprimés ou non.

    Exemples (dossier temporaire : a.log et b.log ont 10 jours, c.log vient d'être créé) :
        >>> import os, tempfile
        >>> d = Path(tempfile.mkdtemp())
        >>> for name, age in [("a.log", 10), ("b.log", 10), ("c.log", 0), ("d.txt", 10)]:
        ...     p = d / name
        ...     p.touch()
        ...     t = time.time() - age * 86400
        ...     os.utime(p, (t, t))
        >>> [p.name for p in clean_old_files(d, days=7)]
        ['a.log', 'b.log']
        >>> sorted(p.name for p in d.iterdir())
        ['a.log', 'b.log', 'c.log', 'd.txt']
        >>> [p.name for p in clean_old_files(d, days=7, dry_run=False)]
        ['a.log', 'b.log']
        >>> sorted(p.name for p in d.iterdir())
        ['c.log', 'd.txt']
    """
    # TODO 13 : horodatage limite : maintenant, moins `days` jours exprimés en secondes.
    # Aide : le module time donne l'heure actuelle en secondes depuis 1970 ; combien de secondes par jour ?
    limit = time.time() - days * 86400
    # TODO 14 : fichiers de folder qui correspondent à pattern, qui sont bien des fichiers, et dont la
    #           date de dernière modification est antérieure à limit ; le tout trié.
    # Aide : doc-3.pdf, partie 3, tableau « Brique Python » : trois de ses briques, plus sorted.
    old: list[Path] = sorted(
        p for p in Path(folder).glob(pattern) if p.is_file() and p.stat().st_mtime < limit
    )
    # Traitement de chaque vieux fichier
    for p in old:
        # Simulation : on annonce, on ne touche à rien
        if dry_run:
            # %s est remplacé par le chemin ; logging ne construit le message que s'il l'affiche
            log.info("[dry-run] supprimerait %s", p)
        # Mode réel, demandé explicitement par --force
        else:
            # TODO 15 : supprimer le fichier p, sans erreur s'il a déjà disparu.
            # Aide : une méthode de Path ; regardez son paramètre facultatif dans la documentation.
            p.unlink(missing_ok=True)
            # Trace de chaque suppression
            log.info("supprimé %s", p)
    # Liste des fichiers concernés
    return old


# ======================================================================================================
# Lab 3.3 — Sockets : tester ports et services
# ======================================================================================================

# Le résultat est un couple : (le port répond ?, temps de connexion en ms, ou None)
def port_check(host: str, port: int, timeout: float = 2.0) -> tuple[bool, int | None]:
    """Teste une connexion TCP vers host:port et mesure son temps d'établissement (lab 3.3).

    Paramètres :
        host : nom ou adresse IP, par exemple « 127.0.0.1 ».
        port : port TCP, par exemple 5432.
        timeout : délai maximal de connexion, en secondes.

    Renvoie :
        (True, durée en millisecondes arrondie à l'entier) si le port accepte la connexion ;
        (False, None) sinon : refus, délai dépassé ou nom inconnu.

    Exemples (un serveur TCP temporaire, ouvert puis fermé) :
        >>> srv = socket.create_server(("127.0.0.1", 0))
        >>> port = srv.getsockname()[1]
        >>> ok, ms = port_check("127.0.0.1", port)
        >>> ok, isinstance(ms, int)
        (True, True)
        >>> srv.close()
        >>> port_check("127.0.0.1", port, timeout=0.5)
        (False, None)
    """
    # Top départ du chronomètre ; perf_counter ne recule jamais, contrairement à l'horloge du système
    start = time.perf_counter()
    # Bloc surveillé : refus, délai dépassé et nom inconnu lèvent tous une OSError
    try:
        # TODO 17 : ouvrir une connexion TCP vers (host, port) avec le timeout, la refermer aussitôt,
        #           et renvoyer True avec la durée écoulée depuis start, en millisecondes arrondies.
        # Aide : doc-3.pdf, partie 4 (fonction try_connect) ; un bloc with referme la connexion tout seul.
        with socket.create_connection((host, port), timeout=timeout):
            return True, round((time.perf_counter() - start) * 1000)
    # Toutes les erreurs réseau dérivent d'OSError : une seule clause except suffit
    except OSError:
        # Le port ne répond pas : pas de durée
        return False, None


# Le résultat est un couple : (le service répond 200 ?, code HTTP, ou None)
def http_check(url: str, timeout: float = 2.0) -> tuple[bool, int | None]:
    """Teste un service au niveau applicatif : la requête GET aboutit-elle avec le code 200 ? (lab 3.3)

    Paramètres :
        url : adresse complète, par exemple « http://127.0.0.1:8000/health ».
        timeout : délai maximal en secondes ; sans lui, requests peut attendre indéfiniment.

    Renvoie :
        (True, 200) si le service répond 200 ; (False, code HTTP) pour un autre code ;
        (False, None) si la connexion échoue ou dépasse le délai.

    Résultats attendus avec le labo :
        /health donne (True, 200) ; /flaky donne (False, 500) ; /slow avec timeout=2 donne (False, None).
    """
    # Bloc surveillé : toute erreur de requests devient un résultat KO
    try:
        # TODO 18 : envoyer une requête GET vers url, avec le timeout.
        # Aide : doc-3.pdf, partie 5, « Rappels sur requests ».
        response = requests.get(url, timeout=timeout)
    # Connexion impossible, délai dépassé… : toutes ces exceptions dérivent de RequestException
    except requests.RequestException:
        # Pas de réponse, donc pas de code HTTP
        return False, None
    # TODO 19 : renvoyer (service OK ?, code HTTP) ; le service n'est OK qu'avec le code 200.
    # Aide : le code HTTP est un attribut de la réponse ; une comparaison donne le booléen.
    return response.status_code == 200, response.status_code


# job est un triplet (nom du serveur, hôte, port) ; la fonction renvoie le résultat de ce test
def check_job(job: tuple[str, str, int], timeout: float = 2.0) -> dict:
    """Teste un port d'un serveur et met le résultat en forme (lab 3.3).

    Paramètres :
        job : (nom du serveur, hôte, port), par exemple ("db-prod", "127.0.0.1", 5432).
        timeout : délai maximal de connexion, en secondes.

    Renvoie :
        {"name": nom, "host": hôte, "port": port, "ok": True ou False, "ms": durée en ms ou None}.
    """
    # Déballage du triplet en trois variables
    name, host, port = job
    # TODO 20 : tester ce port avec la fonction du TODO 17, en lui transmettant le timeout.
    # Aide : cette fonction renvoie déjà le couple attendu ici.
    ok, ms = port_check(host, port, timeout)
    # Résultat complet, prêt à être affiché par cmd_health
    return {"name": name, "host": host, "port": port, "ok": ok, "ms": ms}


# workers est le nombre de threads : 1 pour tester en séquence
def check_targets(servers: list[dict], workers: int = 10, timeout: float = 2.0) -> list[dict]:
    """Teste tous les ports de tous les serveurs (lab 3.3), en parallèle (lab 3.4).

    Paramètres :
        servers : serveurs de l'inventaire, chacun avec « name », « host » et la liste « ports ».
        workers : nombre de threads ; 1 pour tester en séquence.
        timeout : délai maximal de chaque connexion, en secondes.

    Renvoie :
        Un résultat check_job() par port, dans l'ordre des serveurs, puis de leurs ports.

    Exemple (un serveur TCP temporaire, déclaré avec deux fois le même port) :
        >>> srv = socket.create_server(("127.0.0.1", 0))
        >>> port = srv.getsockname()[1]
        >>> servers = [{"name": "local", "host": "127.0.0.1", "ports": [port, port]}]
        >>> [(r["name"], r["port"] == port, r["ok"]) for r in check_targets(servers)]
        [('local', True, True), ('local', True, True)]
        >>> srv.close()
    """
    # TODO 21 : un triplet (nom, hôte, port) pour CHAQUE port de CHAQUE serveur, dans cet ordre.
    # Aide : une compréhension de liste peut contenir deux « for » ; le premier parcourt les serveurs.
    jobs: list[tuple[str, str, int]] = [(s["name"], s["host"], port) for s in servers for port in s["ports"]]
    # Un seul thread demandé : test en séquence, un port après l'autre (version du lab 3.3)
    if workers <= 1:
        # Les attentes s'additionnent : N ports muets coûtent N fois le timeout
        return [check_job(job, timeout) for job in jobs]
    # Groupe de threads ; la sortie du bloc with attend la fin de toutes les tâches
    with ThreadPoolExecutor(max_workers=workers) as pool:
        # TODO 23 (lab 3.4) : lancer check_job sur tous les jobs EN PARALLÈLE avec pool, en gardant l'ordre
        #           de jobs. La valeur provisoire donne le bon résultat, mais en séquence.
        # Aide : diapositive 43 et doc-3.pdf, partie 6 ; attention, check_job attend aussi le timeout.
        return list(pool.map(check_job, jobs, [timeout] * len(jobs)))


# ======================================================================================================
# Lab 3.4 — Paralléliser les tests
# ======================================================================================================

# Renvoie le couple (durée en séquence, durée en parallèle), en secondes
def bench(url: str, count: int = 4, timeout: float = 2.0, workers: int = 10) -> tuple[float, float]:
    """Mesure le gain du parallélisme : count appels à http_check(url), en séquence puis en parallèle.

    Lab 3.4. La même mesure s'applique ensuite à check_targets() (TODO 23).

    Paramètres :
        url : adresse testée ; l'endpoint /slow du labo met 5 s à répondre.
        count : nombre d'appels.
        timeout : délai de chaque appel, en secondes.
        workers : nombre de threads pour la mesure en parallèle.

    Renvoie :
        (durée séquentielle, durée parallèle), en secondes arrondies à 0,1.

    Résultat attendu avec http://127.0.0.1:8000/slow, 4 appels et un timeout de 2 s :
        environ (8.0, 2.0) : en séquence, les 4 timeouts s'additionnent ; en parallèle, ils se superposent.
    """
    # Top départ de la mesure en séquence
    start = time.perf_counter()
    # TODO 24 : appeler count fois http_check(url, timeout), l'un après l'autre.
    # Aide : le résultat des appels ne sert pas ici : seule la durée compte.
    for _ in range(count):
        http_check(url, timeout)
    # Durée de la version séquentielle
    sequential = time.perf_counter() - start
    # Top départ de la mesure en parallèle
    start = time.perf_counter()
    # Groupe de threads ; la sortie du bloc with attend la fin de tous les appels
    with ThreadPoolExecutor(max_workers=workers) as pool:
        # TODO 25 : les mêmes count appels, mais confiés au groupe de threads pool.
        # Aide : même méthode du pool qu'au TODO 23 ; la liste à parcourir peut répéter la même URL.
        list(pool.map(http_check, [url] * count, [timeout] * count))
    # Durée de la version parallèle
    parallel = time.perf_counter() - start
    # Les deux durées, arrondies au dixième de seconde
    return round(sequential, 1), round(parallel, 1)


# ======================================================================================================
# Lab 3.5 — SSH avec paramiko
# ======================================================================================================

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

    # TODO 26 : si password vaut None, le lire dans la variable d'environnement OPS_SSH_PASSWORD.
    # Aide : doc-3.pdf, partie 8 ; os.environ se lit comme un dictionnaire, avec ou sans valeur par défaut.
    if password is None:
        password = os.environ.get("OPS_SSH_PASSWORD")
    # Client SSH ; par défaut, il refuse tout serveur absent de known_hosts (RejectPolicy)
    client = paramiko.SSHClient()
    # TODO 27 : AU LABO SEULEMENT, accepter automatiquement la clé d'un serveur inconnu.
    #           En production : known_hosts et RejectPolicy (diapositive 45, règle 4).
    # Aide : diapositive 44, « L'essentiel » : une politique à fixer sur le client, avant la connexion.
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # Bloc surveillé : erreurs de connexion, d'authentification, de clé d'hôte ou de délai
    try:
        # Connexion par mot de passe ; allow_agent et look_for_keys à False : aucune clé locale essayée
        client.connect(host, port=port, username=user, password=password, timeout=timeout,
                       allow_agent=False, look_for_keys=False)
        # TODO 28 : exécuter command avec le timeout ; lire la sortie standard et la sortie d'erreur en
        #           texte, sans espaces autour ; puis le code retour distant. Lire les sorties AVANT
        #           d'attendre le code retour (doc-3.pdf, partie 7, bonnes pratiques).
        # Aide : exec_command renvoie trois « fichiers » ; read() donne des octets ; le code vient du canal.
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
        # TODO 29 : fermer la connexion SSH, quoi qu'il arrive.
        # Aide : une méthode du client ; sans elle, chaque appel laisse une connexion ouverte.
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
    # TODO 30 : ne garder que les serveurs qui ont une clé « ssh_port » dans l'inventaire.
    # Aide : dans data/inventory.yaml, app01 et app02 ont cette clé ; web-prod et db-prod ne l'ont pas.
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


# ======================================================================================================
# Ligne de commande : une fonction par sous-commande, puis l'analyseur et main()
# ======================================================================================================

# Chaque sous-commande reçoit les arguments lus par argparse et renvoie un code retour
def cmd_sysinfo(args: argparse.Namespace) -> int:
    """Sous-commande « sysinfo » : état du poste en JSON (lab 3.1) ou nettoyage de vieux logs (lab 3.2).

    Paramètres :
        args : arguments lus par argparse ; args.alert est le seuil d'alerte disque ; args.clean le
            dossier à nettoyer (None sans l'option), args.days l'âge minimal, args.force l'action réelle.

    Renvoie :
        État du poste : 1 si le disque est en alerte, 0 sinon.
        Nettoyage : 0, ou 2 si le dossier n'existe pas.
    """
    # Sans --clean : état du poste (lab 3.1)
    if not args.clean:
        # État du poste avec le seuil d'alerte demandé
        info = collect(args.alert)
        # Résultat en JSON sur la sortie standard ; les logs vont sur la sortie d'erreur
        print(json.dumps(info, indent=2, ensure_ascii=False))
        # TODO 12 : code retour 1 si le disque est en alerte, 0 sinon ; le JSON contient l'information.
        # Aide : diapositive 39, points de contrôle : « --alert 1 force l'alerte et le code 1 ».
        return 1 if info["disk"]["alert"] else 0
    # Avec --clean : nettoyage (lab 3.2) ; dossier à nettoyer, sous forme de Path
    folder = Path(args.clean)
    # Un dossier absent est une erreur d'usage : on s'arrête avant de chercher quoi que ce soit
    if not folder.is_dir():
        # Message clair, sans trace Python
        log.error("Dossier introuvable : %s", folder)
        # Code 2 : erreur d'usage
        return 2
    # TODO 16 : lister (ou supprimer) les fichiers de folder plus vieux que args.days jours. La simulation
    #           est le comportement par défaut : seule l'option --force supprime vraiment.
    # Aide : diapositive 40, encadré « Le réflexe » ; args.force ne vaut True qu'avec --force.
    files = clean_old_files(folder, days=args.days, dry_run=not args.force)
    # Bilan : nombre de fichiers et nature de l'action
    print(f"{len(files)} fichier(s) {'supprimé(s)' if args.force else 'à supprimer (dry-run)'}")
    # Code 0 : nettoyage terminé
    return 0


# Même signature pour toutes les sous-commandes
def cmd_health(args: argparse.Namespace) -> int:
    """Sous-commande « health » : teste tous les ports de l'inventaire (labs 3.3 et 3.4).

    Affiche une ligne par port : [OK] ou [KO], nom du serveur, hôte:port, temps en ms.

    Paramètres :
        args : arguments lus par argparse ; args.env, args.timeout et args.workers.

    Renvoie :
        0 si tous les ports répondent, 1 si au moins un est KO. Inventaire invalide : 2, via main().
    """
    # Serveurs de l'environnement demandé (socle du jour 2)
    servers = servers_of(load_inventory(args.inventory), args.env)
    # Un résultat par port, en séquence ou en parallèle selon --workers
    results = check_targets(servers, workers=args.workers, timeout=args.timeout)
    # Une ligne par port
    for r in results:
        # « - » quand le port n'a pas répondu : il n'y a pas de durée
        ms = f"{r['ms']} ms" if r["ms"] is not None else "-"
        # État, nom, adresse et durée, alignés en colonnes
        print(f"[{'OK' if r['ok'] else 'KO'}] {r['name']:<13}{r['host']}:{r['port']:<6} {ms}")
    # TODO 22 : code retour 1 dès qu'un port est KO, 0 si tous sont OK : cron, la CI ou la supervision
    #           réagiront à ce code.
    # Aide : diapositive 41, encadré « Décision » ; Python a une fonction intégrée qui teste « au moins un ».
    return 1 if any(not r["ok"] for r in results) else 0


# Même signature pour toutes les sous-commandes
def cmd_bench(args: argparse.Namespace) -> int:
    """Sous-commande « bench » : mesure en séquence puis en parallèle sur une URL lente (lab 3.4).

    Paramètres :
        args : arguments lus par argparse ; args.url, args.count, args.timeout et args.workers.

    Renvoie :
        0 : une mesure est un résultat, pas un test.
    """
    # Les deux mesures, en secondes
    sequential, parallel = bench(args.url, args.count, args.timeout, args.workers)
    # Durée de la version séquentielle
    print(f"séquentiel : {sequential:.1f} s")
    # Durée de la version parallèle
    print(f"parallèle  : {parallel:.1f} s")
    # Code 0 : la mesure s'est déroulée
    return 0


# Même signature pour toutes les sous-commandes
def cmd_ssh(args: argparse.Namespace) -> int:
    """Sous-commande « ssh » : exécute une commande sur les serveurs SSH d'un environnement (lab 3.5).

    Paramètres :
        args : arguments lus par argparse ; args.command est la commande, args.env l'environnement.

    Renvoie :
        0 si la commande réussit sur tous les serveurs ; 1 si elle échoue sur au moins un, ou s'il
        n'y a aucun serveur SSH ; 2 si OPS_SSH_PASSWORD n'est pas définie.
    """
    # TODO 31 : condition vraie si la variable d'environnement OPS_SSH_PASSWORD est absente ou vide.
    #           Le script doit s'arrêter AVANT toute connexion, avec un message qui dit quoi faire.
    # Aide : doc-3.pdf, partie 8 (secrets_env.py) ; une chaîne vide est « fausse » pour un if.
    if not os.environ.get("OPS_SSH_PASSWORD"):
        # Message clair : la marche à suivre, sans jamais afficher de secret
        log.error("OPS_SSH_PASSWORD n'est pas définie : export OPS_SSH_PASSWORD=...")
        # Code 2 : erreur de configuration
        return 2
    # Serveurs de l'environnement, puis exécution en parallèle sur ceux qui ont un ssh_port
    results = run_on_servers(servers_of(load_inventory(args.inventory), args.env), args.command)
    # Aucun serveur SSH dans cet environnement : on le signale, sinon le code 1 serait incompréhensible
    if not results:
        # Avertissement sur la sortie d'erreur
        log.warning("Aucun serveur avec ssh_port dans l'environnement %s", args.env)
    # Un bloc par serveur : en-tête, puis la sortie (ou l'erreur)
    for r in results:
        # En-tête : nom, adresse et code retour distant
        print(f"--- {r['name']} ({r['host']}) code={r['code']}")
        # La sortie standard si elle existe, sinon le message d'erreur
        print(r["stdout"] or r["stderr"])
    # Serveurs sur lesquels la commande a échoué
    failed = [r["name"] for r in results if not r["ok"]]
    # 1 si un serveur a échoué ou si aucun serveur n'a été contacté, 0 sinon
    return 1 if failed or not results else 0


# Renvoie l'analyseur de la ligne de commande, prêt à l'emploi
def build_parser() -> argparse.ArgumentParser:
    """Construit l'analyseur de la ligne de commande : options générales et sous-commandes.

    Chaque sous-commande enregistre, avec set_defaults(func=…), la fonction qui la traite.

    Renvoie :
        L'analyseur argparse.
    """
    # Analyseur principal ; prog fixe le nom affiché dans l'aide
    parser = argparse.ArgumentParser(prog="lab3", description="Labs du jour 3 : système et réseau")
    # Option générale : messages de niveau DEBUG
    parser.add_argument("-v", "--verbose", action="store_true", help="logs détaillés (DEBUG)")
    # Option générale : chemin de l'inventaire YAML, utilisé par health et ssh
    parser.add_argument("-i", "--inventory", default="data/inventory.yaml", help="fichier d'inventaire YAML")
    # Groupe des sous-commandes ; required=True oblige à en choisir une
    sub = parser.add_subparsers(dest="command_name", required=True)

    # Labs 3.1 et 3.2 : « sysinfo [--alert N] » ou « sysinfo --clean DOSSIER [--days N] [--force] »
    p = sub.add_parser("sysinfo", help="état du poste en JSON, ou nettoyage de vieux logs (labs 3.1 et 3.2)")
    # Seuil d'alerte disque ; %% affiche un « % » littéral dans l'aide
    p.add_argument("--alert", type=int, default=80, help="seuil d'alerte disque en %% (défaut : 80)")
    # Dossier à nettoyer ; sans l'option, la sous-commande affiche l'état du poste
    p.add_argument("--clean", metavar="DOSSIER", help="nettoyer les .log anciens de ce dossier")
    # Âge minimal des fichiers à nettoyer, en jours
    p.add_argument("--days", type=int, default=7, help="âge minimal en jours (défaut : 7)")
    # Drapeau de l'action réelle : sans lui, simple simulation
    p.add_argument("--force", action="store_true", help="supprimer réellement (sinon : dry-run)")
    # Fonction appelée par main() pour cette sous-commande
    p.set_defaults(func=cmd_sysinfo)

    # Labs 3.3 et 3.4 : « health [--env ENV] [--timeout S] [--workers N] »
    p = sub.add_parser("health", help="tester les ports de l'inventaire (labs 3.3 et 3.4)")
    # Environnement à tester ; sans l'option, tous les environnements
    p.add_argument("--env", help="dev, recette ou prod (défaut : tous)")
    # Délai de chaque connexion, en secondes
    p.add_argument("--timeout", type=float, default=2.0, help="timeout de chaque test en s (défaut : 2)")
    # Nombre de threads ; 1 donne la version séquentielle
    p.add_argument("--workers", type=int, default=10, help="tests simultanés ; 1 = en séquence (défaut : 10)")
    # Fonction appelée par main() pour cette sous-commande
    p.set_defaults(func=cmd_health)

    # Lab 3.4 : « bench [URL] [--count N] [--timeout S] [--workers N] »
    p = sub.add_parser("bench", help="mesurer séquentiel et parallèle sur une URL lente (lab 3.4)")
    # URL facultative ; nargs="?" accepte zéro ou une valeur
    p.add_argument("url", nargs="?", default="http://127.0.0.1:8000/slow", help="URL (défaut : /slow)")
    # Nombre d'appels de chaque mesure
    p.add_argument("--count", type=int, default=4, help="nombre d'appels (défaut : 4)")
    # Délai de chaque appel, en secondes
    p.add_argument("--timeout", type=float, default=2.0, help="timeout de chaque appel en s (défaut : 2)")
    # Nombre de threads de la mesure en parallèle
    p.add_argument("--workers", type=int, default=10, help="threads de la mesure parallèle (défaut : 10)")
    # Fonction appelée par main() pour cette sous-commande
    p.set_defaults(func=cmd_bench)

    # Lab 3.5 : « ssh "COMMANDE" [--env ENV] »
    p = sub.add_parser("ssh", help="exécuter une commande sur les serveurs SSH (lab 3.5)")
    # Commande à exécuter, entre guillemets si elle contient des espaces
    p.add_argument("command", help='commande à exécuter, par exemple "hostname && uptime -p"')
    # Environnement visé ; prod contient app01 et app02
    p.add_argument("--env", default="prod", help="environnement (défaut : prod)")
    # Fonction appelée par main() pour cette sous-commande
    p.set_defaults(func=cmd_ssh)

    # Renvoi de l'analyseur complet
    return parser


# argv vaut None par défaut : argparse lit alors la vraie ligne de commande
def main(argv: list[str] | None = None) -> int:
    """Point d'entrée : lit la ligne de commande, lance la sous-commande, gère les erreurs prévues.

    Paramètres :
        argv : arguments de la ligne de commande ; None (défaut) lit sys.argv. Un test peut
            passer une liste, par exemple ["health", "--env", "prod"].

    Renvoie :
        Le code retour de la sous-commande, ou 2 pour une erreur d'inventaire.
    """
    # Lecture des arguments ; une option inconnue affiche l'usage et quitte avec le code 2
    args = build_parser().parse_args(argv)
    # Niveau DEBUG avec -v, INFO sinon ; format « NIVEAU message » ; les logs vont sur stderr
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")
    # paramiko journalise chaque authentification en INFO : on ne garde que ses avertissements
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    # Exécution surveillée : une erreur d'inventaire devient un message clair et le code 2
    try:
        # Appel de la fonction enregistrée par la sous-commande choisie
        return args.func(args)
    # Inventaire invalide ou environnement inconnu (socle du jour 2)
    except InventoryError as exc:
        # Message clair, sans trace Python
        log.error("%s", exc)
        # Code 2 : erreur de configuration
        return 2


# Condition vraie seulement quand le fichier est lancé directement, pas quand il est importé
if __name__ == "__main__":
    # Lance main() et transmet son code retour au shell, visible avec « echo $? »
    sys.exit(main())

