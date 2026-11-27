# watchdog.py - verifie des services (port TCP + URL de sante) et ecrit un rapport JSON.
# Usage : python watchdog.py FICHIER_CIBLES [-o RAPPORT] [-v]
# Codes retour : 0 = tout OK, 1 = au moins une cible KO, 2 = fichier invalide / argument manquant.
import argparse
import json
import logging
import socket
import sys
import time

import requests
import yaml

logger = logging.getLogger("watchdog")


def load_targets(path):
    # Lit et valide le YAML ; leve ValueError si le fichier est invalide.
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except OSError as e:
        raise ValueError(str(e)) from e
    except yaml.YAMLError as e:
        raise ValueError(f"YAML illisible : {e}") from e

    if not isinstance(data, dict) or not isinstance(data.get("targets"), list):
        raise ValueError("cle targets absente ou pas une liste")

    targets = data["targets"]
    for i, t in enumerate(targets):
        if not isinstance(t, dict):
            raise ValueError(f"cible numero {i + 1} invalide")
        for key in ("name", "host", "port"):
            if key not in t or t[key] in (None, ""):
                raise ValueError(f"cible numero {i + 1} : champ {key} manquant")
        if not isinstance(t["port"], int):
            raise ValueError(f"cible numero {i + 1} : port doit etre un entier")
    return targets


def check_port(host, port, timeout=2.0):
    # Renvoie (True, ms) si le port repond, sinon (False, None).
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            ms = int((time.perf_counter() - start) * 1000)
            return True, ms
    except OSError:
        return False, None


def check_http(url, timeout=2.0):
    # True seulement pour un statut 200 ; ne leve jamais d exception.
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except requests.RequestException:
        return False


def check_target(target):
    # Combine le test du port et le test HTTP ; renvoie l entree du rapport.
    ok, ms = check_port(target["host"], target["port"])
    logger.debug("%s : port %s:%s -> %s (%s ms)",
                 target["name"], target["host"], target["port"], ok, ms)
    if ok and target.get("health_url"):
        ok = check_http(target["health_url"])
        logger.debug("%s : GET %s -> %s", target["name"], target["health_url"], ok)
    return {"name": target["name"], "ok": ok, "ms": ms}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verifie des services et ecrit un rapport JSON.")
    parser.add_argument("fichier", help="fichier YAML des cibles")
    parser.add_argument("-o", "--output", default="watchdog-report.json",
                        help="chemin du rapport (defaut : watchdog-report.json)")
    parser.add_argument("-v", "--verbose", action="store_true", help="niveau DEBUG")
    args = parser.parse_args(argv)  # argparse fait sys.exit(2) si argument manquant

    logging.basicConfig(format="%(levelname)s %(message)s",
                        level=logging.DEBUG if args.verbose else logging.INFO,
                        force=True)

    try:
        targets = load_targets(args.fichier)
    except ValueError as e:
        logger.error("Fichier de cibles invalide : %s", e)
        return 2

    report = []
    for target in targets:
        entry = check_target(target)
        logger.info("%s : %s", entry["name"], "OK" if entry["ok"] else "KO")
        report.append(entry)

    try:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    except OSError as e:
        logger.error("Impossible d ecrire le rapport : %s", e)
        return 2

    return 0 if all(e["ok"] for e in report) else 1


if __name__ == "__main__":
    sys.exit(main())
