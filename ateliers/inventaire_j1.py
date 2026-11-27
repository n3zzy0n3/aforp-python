"""Corrigé des labs 1.2, 1.4 et 1.5 : inventaire en ligne de commande (version mono-fichier du jour 1).

Le script lit un fichier JSON de serveurs, vérifie que chaque serveur est complet, affiche un tableau
trié par CPU décroissant et signale dans le journal les serveurs arrêtés ou en surcharge.

Usage : python inventaire_j1.py data/servers.json --role web --threshold 80 -v
Codes retour : 0 = parc sain, 2 = au moins un serveur arrêté ou en surcharge, 3 = fichier invalide.
"""
# argparse lit les arguments de la ligne de commande et génère l'aide --help
import argparse
# json convertit le texte du fichier en listes et dictionnaires Python
import json
# logging écrit les messages de suivi avec un niveau : DEBUG, INFO, WARNING, ERROR
import logging
# sys donne accès à sys.exit, qui transmet le code retour au shell
import sys

# Journal propre à ce script : son nom « inventaire » le distingue des journaux des autres modules
log = logging.getLogger("inventaire")
# Champs obligatoires de chaque serveur ; un tuple, car cette liste ne change jamais
REQUIRED = ("name", "ip", "role", "cpu", "up")


# Exception personnalisée : elle hérite d'Exception, la classe de base des erreurs courantes
class InventaireInvalide(Exception):
    """Le fichier d'inventaire est absent, illisible ou incomplet.

    Exception métier levée par load_servers(). main() l'attrape pour afficher un message clair
    et renvoyer le code 3, au lieu d'une trace Python incompréhensible pour l'exploitant.
    """


# Annotations : path est une chaîne, la fonction renvoie une liste de dictionnaires
def load_servers(path: str) -> list[dict]:
    """Charge le fichier JSON des serveurs et vérifie chaque serveur (lab 1.5).

    Paramètres :
        path : chemin du fichier JSON, par exemple « data/servers.json ».

    Renvoie :
        La liste des serveurs, un dictionnaire par serveur.

    Lève :
        InventaireInvalide : fichier introuvable, JSON mal formé ou champ obligatoire manquant.
    """
    # Bloc surveillé : les erreurs de lecture y sont transformées en InventaireInvalide
    try:
        # Ouverture en lecture et en UTF-8 ; with referme le fichier, même en cas d'erreur
        with open(path, encoding="utf-8") as f:
            # Conversion du contenu JSON en objets Python : ici, une liste de dictionnaires
            servers = json.load(f)
    # Premier cas d'erreur : le fichier n'existe pas
    except FileNotFoundError as exc:
        # Message lisible ; « from exc » conserve l'erreur d'origine pour le débogage
        raise InventaireInvalide(f"Fichier introuvable : {path}") from exc
    # Second cas d'erreur : le fichier existe, mais son contenu n'est pas du JSON valide
    except json.JSONDecodeError as exc:
        # exc.lineno donne la ligne fautive et exc.msg la nature de l'erreur
        raise InventaireInvalide(f"JSON invalide ligne {exc.lineno} : {exc.msg}") from exc
    # Parcours des serveurs, numérotés à partir de 1 pour que le message parle à un humain
    for i, server in enumerate(servers, start=1):
        # Champs obligatoires absents de ce serveur (liste vide si le serveur est complet)
        missing = [k for k in REQUIRED if k not in server]
        # Une liste non vide est « vraie » : au moins un champ manque
        if missing:
            # On s'arrête ici, avec un message qui désigne le serveur et les champs manquants
            raise InventaireInvalide(f"Serveur n°{i} : champ(s) manquant(s) {', '.join(missing)}")
    # Tous les serveurs sont complets : la liste est renvoyée à l'appelant
    return servers


# Annotations : reçoit une liste de dictionnaires, renvoie un dictionnaire rôle → nombre
def count_by_role(servers: list[dict]) -> dict[str, int]:
    """Compte les serveurs par rôle (lab 1.2).

    Paramètres :
        servers : liste des serveurs, chacun avec une clé « role ».

    Renvoie :
        Un dictionnaire rôle → nombre de serveurs.

    Exemple :
        >>> count_by_role([{"role": "web"}, {"role": "db"}, {"role": "web"}])
        {'web': 2, 'db': 1}
    """
    # Dictionnaire vide qui accumulera les compteurs ; l'annotation précise son contenu
    counts: dict[str, int] = {}
    # Parcours de chaque serveur de la liste
    for s in servers:
        # get renvoie 0 si le rôle n'a pas encore été rencontré ; on ajoute 1 au compteur
        counts[s["role"]] = counts.get(s["role"], 0) + 1
    # Renvoi du dictionnaire complet
    return counts


# Annotations : une liste de serveurs et un seuil entier, renvoie une liste de serveurs
def overloaded(servers: list[dict], threshold: int) -> list[dict]:
    """Sélectionne les serveurs qui demandent une intervention.

    Paramètres :
        servers : liste des serveurs, avec les clés « up » et « cpu ».
        threshold : seuil CPU en pourcentage ; au-delà, le serveur est en surcharge.

    Renvoie :
        Les serveurs arrêtés (« up » faux) ou dont le CPU dépasse strictement le seuil.
    """
    # Compréhension de liste : on garde le serveur s'il est arrêté OU au-dessus du seuil
    return [s for s in servers if not s["up"] or s["cpu"] > threshold]


# Annotations : « -> None » indique que la fonction affiche mais ne renvoie rien
def print_table(servers: list[dict], threshold: int) -> None:
    """Affiche le tableau des serveurs, du CPU le plus élevé au plus faible.

    La colonne ÉTAT vaut KO pour un serveur arrêté, SURCHARGE au-delà du seuil, OK sinon.
    Ce tableau est le résultat du script : il passe par print, et non par logging.

    Paramètres :
        servers : liste des serveurs à afficher.
        threshold : seuil CPU en pourcentage qui déclenche l'état SURCHARGE.
    """
    # En-tête : :<10 aligne à gauche sur 10 caractères, :>5 aligne à droite sur 5
    print(f"{'NOM':<10}{'IP':<12}{'RÔLE':<8}{'CPU':>5}  ÉTAT")
    # Tri par CPU décroissant : key choisit le critère de tri, reverse=True inverse l'ordre
    for s in sorted(servers, key=lambda s: s["cpu"], reverse=True):
        # État du serveur : KO s'il est arrêté, sinon SURCHARGE ou OK selon le seuil
        state = "KO" if not s["up"] else ("SURCHARGE" if s["cpu"] > threshold else "OK")
        # Une ligne par serveur, avec les mêmes largeurs de colonnes que l'en-tête
        print(f"{s['name']:<10}{s['ip']:<12}{s['role']:<8}{s['cpu']:>4}%  {state}")


# argv vaut None par défaut ; « list[str] | None » signifie « liste de chaînes, ou None »
def main(argv: list[str] | None = None) -> int:
    """Point d'entrée du script : lit les options, charge l'inventaire, affiche le tableau (lab 1.4).

    Paramètres :
        argv : arguments de la ligne de commande. Avec None (valeur par défaut), argparse lit
            sys.argv ; un test peut passer une liste, par exemple ["data/servers.json", "-v"].

    Renvoie :
        Le code retour : 0 si le parc est sain, 2 si au moins un serveur est arrêté ou en
        surcharge, 3 si le fichier est invalide.
    """
    # Analyseur des arguments ; la description s'affiche en tête de --help
    parser = argparse.ArgumentParser(description="Inventaire du parc CloudNova")
    # Argument positionnel, donc obligatoire : le chemin du fichier JSON
    parser.add_argument("file", help="fichier JSON des serveurs")
    # Option facultative pour filtrer sur un rôle ; elle vaut None si elle est absente
    parser.add_argument("--role", help="n'afficher que ce rôle")
    # Seuil CPU converti en entier par type=int ; %% affiche un « % » littéral dans l'aide
    parser.add_argument("--threshold", type=int, default=80, help="seuil CPU en %% (défaut : 80)")
    # Drapeau : action="store_true" donne True si -v est présent, False sinon
    parser.add_argument("-v", "--verbose", action="store_true")
    # Lecture des arguments ; s'ils sont incorrects, argparse affiche l'usage et quitte (code 2)
    args = parser.parse_args(argv)
    # Configuration du journal : niveau DEBUG avec -v, INFO sinon ; format « NIVEAU message »
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")
    # Chargement surveillé : un fichier invalide ne doit pas produire de trace Python
    try:
        # Lecture et vérification du fichier JSON
        servers = load_servers(args.file)
    # Fichier introuvable, JSON invalide ou champ manquant
    except InventaireInvalide as exc:
        # Message d'erreur clair dans le journal, au niveau ERROR
        log.error("%s", exc)
        # Code 3 : le fichier est invalide
        return 3
    # Détail affiché seulement avec -v : nombre de serveurs et répartition par rôle
    log.debug("%d serveurs chargés, répartition %s", len(servers), count_by_role(servers))
    # Si l'option --role a été donnée…
    if args.role:
        # … on ne garde que les serveurs de ce rôle
        servers = [s for s in servers if s["role"] == args.role]
    # Affichage du tableau : c'est le résultat du script
    print_table(servers, args.threshold)
    # Liste des serveurs arrêtés ou en surcharge
    bad = overloaded(servers, args.threshold)
    # Un avertissement pour chaque serveur à traiter
    for s in bad:
        # logging remplace %s par le nom, et ne construit le message que s'il l'affiche
        log.warning("%s nécessite une intervention", s["name"])
    # Code 2 si au moins un serveur pose problème (liste non vide), 0 sinon
    return 2 if bad else 0


# Condition vraie seulement quand le fichier est lancé directement, pas quand il est importé
if __name__ == "__main__":
    # Lance main() et transmet son code retour au shell, visible avec « echo $? »
    sys.exit(main())
