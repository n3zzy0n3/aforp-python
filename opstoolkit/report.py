"""Rapports Markdown et HTML avec Jinja2 (lab 2.5)."""
from datetime import datetime

from jinja2 import Environment

# Gabarit Markdown ; {{ … }} affiche une valeur, {% … %} est une instruction, {# … #} un commentaire
MARKDOWN = """# Rapport d'exploitation CloudNova — {{ generated }}

## Inventaire ({{ servers | length }} serveurs)

| Environnement | Serveur | Rôle | Hôte | Ports |
| --- | --- | --- | --- | --- |
{% for s in servers %}| {{ s.env }} | {{ s.name }} | {{ s.role }} | {{ s.host }} | {{ s.ports | join(', ') }} |
{% endfor %}
{% if health %}
## État des services

| Serveur | Port | État | Temps (ms) |
| --- | --- | --- | --- |
{% for h in health -%}
| {{ h.name }} | {{ h.port }} | {{ 'OK' if h.ok else 'KO' }} | {{ h.ms if h.ms is not none else '-' }} |
{% endfor %}{% endif %}
"""


# Gabarit HTML, complet : une page autonome avec son style et un tableau des serveurs
HTML = """<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Rapport CloudNova</title><style>
body{font-family:sans-serif;margin:2rem;color:#1b2a4a}h1{color:#1d3a6e}
table{border-collapse:collapse}td,th{border:1px solid #ccd;padding:.3rem .6rem}
th{background:#1d3a6e;color:#fff}</style></head><body>
<h1>Rapport d'exploitation CloudNova</h1><p>Généré le {{ generated }}</p>
<table><tr><th>Environnement</th><th>Serveur</th><th>Rôle</th><th>Hôte</th><th>Ports</th></tr>
{% for s in servers %}<tr><td>{{ s.env }}</td><td>{{ s.name }}</td><td>{{ s.role }}</td>
<td>{{ s.host }}</td><td>{{ s.ports | join(', ') }}</td></tr>{% endfor %}</table>
{% if health %}<h2>État des services</h2>
<table><tr><th>Serveur</th><th>Port</th><th>État</th></tr>
{% for h in health %}<tr><td>{{ h.name }}</td><td>{{ h.port }}</td>
<td>{{ 'OK' if h.ok else 'KO' }}</td></tr>{% endfor %}</table>{% endif %}
</body></html>"""


# fmt vaut "md" par défaut ; la fonction renvoie le texte du rapport
def render(servers: list[dict], health: list[dict] | None = None, fmt: str = "md") -> str:
    """Produit le rapport d'inventaire au format Markdown ou HTML (lab 2.5).

    Avec health, le rapport ajoute l'état des services (option --with-health, lab 3.3).

    Paramètres :
        servers : serveurs renvoyés par servers_of(), avec la clé « env ».
        health : résultats de check_targets(), ou None pour ne pas afficher l'état des services.
        fmt : « md » pour Markdown (défaut) ou « html ».

    Renvoie :
        Le texte du rapport.

    Exemple :
        >>> servers = [{"env": "prod", "name": "web-prod", "role": "web",
        ...             "host": "127.0.0.1", "ports": [8081]}]
        >>> "| prod | web-prod | web | 127.0.0.1 | 8081 |" in render(servers)
        True
        >>> pirate = [{**servers[0], "name": "<b>pirate</b>"}]
        >>> "&lt;b&gt;pirate&lt;/b&gt;" in render(pirate, fmt="html")
        True
    """
    env = Environment(autoescape=fmt == "html")
    template = env.from_string(HTML if fmt == "html" else MARKDOWN)
    # Remplissage du gabarit : servers et generated deviennent des variables du gabarit
    return template.render(servers=servers, health=health or [], generated=datetime.now().strftime("%d/%m/%Y %H:%M"))
