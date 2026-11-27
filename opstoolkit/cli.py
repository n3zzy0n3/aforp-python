"""Point d'entrée en ligne de commande d'OpsToolkit (lab 1.4, enrichi chaque jour).

Codes retour : 0 = tout va bien, 1 = au moins une cible KO (port, composant, conteneur),
2 = erreur d'usage, de configuration ou d'appel.
"""
import argparse
import json
import logging
import sys
from pathlib import Path

from . import __version__
from .api import StatusApiError
from .backup import BackupError
from .inventory import InventoryError

log = logging.getLogger("opstoolkit")


def cmd_inventory(args) -> int:
    from .inventory import load_inventory, servers_of
    servers = servers_of(load_inventory(args.inventory), args.env)
    print(f"{'ENV':<9}{'NOM':<13}{'RÔLE':<9}{'HÔTE':<12}PORTS")
    for s in servers:
        print(f"{s['env']:<9}{s['name']:<13}{s['role']:<9}{s['host']:<12}{','.join(map(str, s['ports']))}")
    return 0


def cmd_logs(args) -> int:
    from .logs import analyze
    report = analyze(args.file, args.top)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("Rapport écrit dans %s", args.output)
    return 0


def cmd_report(args) -> int:
    from .health import check_targets
    from .inventory import load_inventory, servers_of
    from .report import render
    servers = servers_of(load_inventory(args.inventory), args.env)
    health = check_targets(servers) if args.with_health else None
    content = render(servers, health, args.format)
    Path(args.output).write_text(content, encoding="utf-8")
    print(f"Rapport écrit dans {args.output}")
    return 0


def cmd_sysinfo(args) -> int:
    from .sysinfo import clean_old_files, collect
    if args.clean:
        files = clean_old_files(args.clean, days=args.days, dry_run=not args.force)
        print(f"{len(files)} fichier(s) {'supprimé(s)' if args.force else 'à supprimer (dry-run)'}")
        return 0
    info = collect(args.alert)
    print(json.dumps(info, indent=2, ensure_ascii=False))
    return 1 if info["disk"]["alert"] else 0


def cmd_health(args) -> int:
    from .health import check_targets
    from .inventory import load_inventory, servers_of
    results = check_targets(servers_of(load_inventory(args.inventory), args.env), timeout=args.timeout)
    for r in results:
        state = "OK" if r["ok"] else "KO"
        ms = f"{r['ms']} ms" if r["ms"] is not None else "-"
        print(f"[{state}] {r['name']:<13}{r['host']}:{r['port']:<6} {ms}")
    failed = [f"{r['name']}:{r['port']}" for r in results if not r["ok"]]
    if failed and args.notify:
        from .extras import notify
        notify("OpsToolkit : services KO -> " + ", ".join(failed))
    return 1 if failed else 0


def cmd_ssh(args) -> int:
    from .inventory import load_inventory, servers_of
    from .sshrun import run_on_servers
    results = run_on_servers(servers_of(load_inventory(args.inventory), args.env), args.command)
    for r in results:
        print(f"--- {r['name']} ({r['host']}) code={r['code']}\n{r['stdout'] or r['stderr']}")
    return 0 if results and all(r["ok"] for r in results) else 1


def cmd_api(args) -> int:
    from .api import StatusClient
    client = StatusClient(args.url)
    degraded = client.degraded()
    for c in degraded:
        print(f"[DÉGRADÉ] {c['name']} : {c['status']}")
        if args.create_incidents:
            incident = client.create_incident(c["name"], f"{c['name']} en {c['status']}", "major")
            print(f"  incident n°{incident['id']} créé")
    if not degraded:
        print("Tous les composants sont opérationnels")
    return 1 if degraded else 0


def cmd_serve(args) -> int:
    import uvicorn

    from .server import create_app
    log.info("Documentation : http://%s:%d/docs", args.host, args.port)
    uvicorn.run(create_app(args.inventory), host=args.host, port=args.port)
    return 0


def cmd_docker(args) -> int:
    import docker

    from .extras import container_logs, lab_containers, restart_stopped
    try:
        if args.logs:
            print(container_logs(args.logs))
            return 0
        if args.restart:
            for name in restart_stopped():
                print(f"Redémarré : {name}")
        containers = lab_containers()
    except docker.errors.NotFound:
        log.error("Conteneur introuvable : %s", args.logs)
        return 2
    except docker.errors.DockerException as exc:
        log.error("Docker injoignable : %s", exc)
        return 2
    if not containers:
        log.warning("Aucun conteneur lab-… : cd ~/lab && docker compose up -d")
        return 1
    for c in containers:
        print(f"{c['name']:<16}{c['status']:<10}{c['image']}")
    return 1 if any(c["status"] != "running" for c in containers) else 0


def cmd_backup(args) -> int:
    from .backup import backup
    result = backup(args.folder, args.bucket, args.keep)
    print(f"Envoyé : {result['uploaded']}")
    for key in result["deleted"]:
        print(f"Rotation : {key} supprimé")
    return 0


def cmd_exporter(args) -> int:
    from .extras import start_exporter
    from .inventory import load_inventory, servers_of
    servers = servers_of(load_inventory(args.inventory), args.env)
    try:
        start_exporter(servers, port=args.port, interval=args.interval)
    except KeyboardInterrupt:
        log.info("Exporteur arrêté")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opstoolkit", description="Boîte à outils d'exploitation CloudNova")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="logs détaillés (DEBUG)")
    parser.add_argument("-i", "--inventory", default="data/inventory.yaml", help="fichier d'inventaire YAML")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inventory", help="afficher l'inventaire")
    p.add_argument("--env")
    p.set_defaults(func=cmd_inventory)

    p = sub.add_parser("logs", help="analyser un log Nginx")
    p.add_argument("file")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("-o", "--output", help="écrire le rapport JSON dans ce fichier")
    p.set_defaults(func=cmd_logs)

    p = sub.add_parser("report", help="générer un rapport Markdown ou HTML")
    p.add_argument("--env")
    p.add_argument("--format", choices=["md", "html"], default="md")
    p.add_argument("-o", "--output", default="rapport.md")
    p.add_argument("--with-health", action="store_true")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("sysinfo", help="état du poste ou nettoyage de logs")
    p.add_argument("--alert", type=int, default=80, help="seuil d'alerte disque en %%")
    p.add_argument("--clean", metavar="DOSSIER", help="nettoyer les .log anciens de ce dossier")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--force", action="store_true", help="supprimer réellement (sinon dry-run)")
    p.set_defaults(func=cmd_sysinfo)

    p = sub.add_parser("health", help="tester les ports de l'inventaire")
    p.add_argument("--env")
    p.add_argument("--timeout", type=float, default=2.0)
    p.add_argument("--notify", action="store_true", help="alerter via OPS_WEBHOOK_URL si un port est KO")
    p.set_defaults(func=cmd_health)

    p = sub.add_parser("ssh", help="exécuter une commande sur les serveurs SSH")
    p.add_argument("command")
    p.add_argument("--env", default="prod")
    p.set_defaults(func=cmd_ssh)

    p = sub.add_parser("api", help="composants dégradés de l'API de statut")
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--create-incidents", action="store_true", help="créer un incident par composant dégradé")
    p.set_defaults(func=cmd_api)

    p = sub.add_parser("serve", help="lancer l'API d'OpsToolkit (FastAPI)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8090)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("docker", help="conteneurs du labo avec le SDK Docker")
    p.add_argument("--restart", action="store_true", help="redémarrer les conteneurs lab- arrêtés")
    p.add_argument("--logs", metavar="NOM", help="afficher les 5 dernières lignes du journal de NOM")
    p.set_defaults(func=cmd_docker)

    p = sub.add_parser("backup", help="sauvegarder un dossier vers S3 / MinIO")
    p.add_argument("folder")
    p.add_argument("--bucket", default="cloudnova-backups")
    p.add_argument("--keep", type=int, default=5)
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("exporter", help="exporteur Prometheus des ports de l'inventaire")
    p.add_argument("--env")
    p.add_argument("--port", type=int, default=9105)
    p.add_argument("--interval", type=int, default=15)
    p.set_defaults(func=cmd_exporter)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")
    try:
        return args.func(args)
    except (InventoryError, FileNotFoundError, StatusApiError, BackupError) as exc:  # erreurs prévues
        log.error("%s", exc)
        return 2
    except ModuleNotFoundError as exc:  # bibliothèque du jour pas encore installée
        log.error("Bibliothèque absente : %s (pip install …)", exc.name)
        return 2


if __name__ == "__main__":
    sys.exit(main())
