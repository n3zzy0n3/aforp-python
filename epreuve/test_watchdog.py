# Tests de watchdog.py - aucun appel reseau reel, aucun labo necessaire.
import json
from unittest.mock import Mock, patch

import watchdog


def test_fichier_absent_renvoie_2(tmp_path):
    code = watchdog.main([str(tmp_path / "absent.yaml")])
    assert code == 2


def test_yaml_sans_port_renvoie_2(tmp_path):
    f = tmp_path / "cibles.yaml"
    f.write_text("targets:\n  - {name: x, host: 127.0.0.1}\n", encoding="utf-8")
    assert watchdog.main([str(f)]) == 2


def test_http_500_est_ko():
    # Simule une reponse HTTP 500 : la cible doit etre KO.
    fake = Mock(status_code=500)
    with patch("watchdog.requests.get", return_value=fake):
        assert watchdog.check_http("http://exemple/flaky") is False


def test_cible_flaky_ko_dans_rapport(tmp_path):
    # Port simule ouvert + HTTP 500 simule -> ok false, code retour 1.
    f = tmp_path / "cibles.yaml"
    f.write_text(
        "targets:\n"
        "  - {name: api-flaky, host: 127.0.0.1, port: 8000,"
        " health_url: \"http://127.0.0.1:8000/flaky\"}\n",
        encoding="utf-8",
    )
    rapport = tmp_path / "rapport.json"
    with patch("watchdog.check_port", return_value=(True, 3)), \
         patch("watchdog.requests.get", return_value=Mock(status_code=500)):
        code = watchdog.main([str(f), "-o", str(rapport)])
    assert code == 1
    assert json.loads(rapport.read_text()) == [{"name": "api-flaky", "ok": False, "ms": 3}]


def test_tout_ok_renvoie_0(tmp_path):
    f = tmp_path / "cibles.yaml"
    f.write_text("targets:\n  - {name: cache, host: 127.0.0.1, port: 6379}\n", encoding="utf-8")
    with patch("watchdog.check_port", return_value=(True, 0)):
        assert watchdog.main([str(f), "-o", str(tmp_path / "r.json")]) == 0
