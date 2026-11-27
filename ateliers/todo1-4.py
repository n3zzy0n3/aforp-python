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
