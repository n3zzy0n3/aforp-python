"""Pilotage du système : subprocess, shutil, pathlib (labs 3.1 et 3.2)."""
import logging
import platform
import shutil
import socket
import subprocess
import sys  # noqa: F401  (utilisé par les exemples de run())
import time
from pathlib import Path

log = logging.getLogger(__name__)


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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    # Le programme n'existe pas sur ce poste (macOS sans « uptime -p », image minimale…)
    except FileNotFoundError:
        return 127, ""
    # Le programme n'a pas répondu à temps : subprocess l'a déjà arrêté
    except subprocess.TimeoutExpired:
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
    total, used, _free = shutil.disk_usage(path)
    pct = round(used / total * 100, 1)
    # Dictionnaire sérialisable en JSON
    return {
        # Point de montage mesuré
        "path": path,
        # Taille totale en Go : 1 Go = 10**9 octets, comme df -H
        "total_gb": round(total / 1e9, 1),
        # Pourcentage calculé au TODO 5
        "used_pct": pct,
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
    code, out = run(["ps", "-eo", "pid,%mem,comm", "--sort=-%mem"])
    # ps a échoué ou n'existe pas : pas de classement, mais pas de plantage non plus
    if code != 0:
        # Liste vide : collect() l'écrira telle quelle dans le JSON
        return []
    # Liste des processus retenus
    procs = []
    for line in out.splitlines()[1:n + 1]:
        # Découpage en 3 morceaux au plus : comm vient en dernier, car un nom peut contenir des espaces
        pid, mem, comm = line.split(None, 2)
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
    code, uptime = run(["uptime", "-p"])
    # Dictionnaire de l'état du poste ; json.dumps le convertira tel quel
    return {
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
    limit = time.time() - days * 86400
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
            p.unlink(missing_ok=True)
            # Trace de chaque suppression
            log.info("supprimé %s", p)
    # Liste des fichiers concernés
    return old
