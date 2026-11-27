"""Analyse de logs Nginx au format combined (lab 2.4)."""
import re
from collections import Counter
from pathlib import Path

# Motif d'une ligne Nginx au format « combined » ; (?P<nom>…) est un groupe nommé, lu avec m["nom"]
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
    match = PATTERN.match(line)
    # Pas de correspondance : la ligne est corrompue ou n'est pas une requête
    if match is None:
        # None signale à l'appelant une ligne à ignorer
        return None
    # Dictionnaire {nom du groupe: texte capturé}
    entry = match.groupdict()
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
            ips[entry["ip"]] += 1
            families[f"{entry['status'] // 100}xx"] += 1
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
        "top_ips": ips.most_common(top),
        # Familles de statut triées par nom : 2xx, 3xx, 4xx, 5xx
        "status_families": dict(sorted(families.items())),
        # Classement des URL en erreur 5xx (second trou du TODO 27)
        "top_5xx_urls": errors_5xx.most_common(top),
    }
