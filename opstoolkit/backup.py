"""Sauvegardes S3 / MinIO avec boto3 (lab 4.4).

MemoryS3 imite un client S3 en mémoire : il sert aux exemples (python -m doctest), sans MinIO.
"""
import hashlib
import logging
import os
import tarfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

log = logging.getLogger(__name__)


# Un dictionnaire par bucket, qui associe chaque clé à la taille et aux métadonnées de l'objet
class MemoryS3:
    """Faux client S3 en mémoire, pour les exemples du lab 4.4 (déjà complet).

    Il imite les méthodes du client boto3 utilisées dans ce fichier : head_bucket, create_bucket,
    upload_file, list_objects_v2, head_object et delete_object. put() dépose un objet vide.

    Paramètres :
        buckets : noms des buckets qui existent dès le départ.
    """

    # Buckets de départ, tous vides
    def __init__(self, buckets: tuple[str, ...] = ()):
        """Crée le faux stockage avec les buckets donnés."""
        # {bucket: {clé: {"Size": taille, "Metadata": {…}}}}
        self.buckets = {name: {} for name in buckets}
        # Région, lue par ensure_bucket() comme client.meta.region_name
        self.meta = SimpleNamespace(region_name="us-east-1")

    # Comme boto3 : ClientError si le bucket n'existe pas
    def head_bucket(self, Bucket: str) -> dict:
        """Vérifie que le bucket existe."""
        if Bucket not in self.buckets:
            # Import ici : botocore n'est installé qu'au lab 4.4, avec boto3
            from botocore.exceptions import ClientError
            raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket")
        return {}

    # Création du bucket ; CreateBucketConfiguration est accepté et ignoré
    def create_bucket(self, Bucket: str, **kwargs) -> dict:
        """Crée le bucket s'il n'existe pas."""
        self.buckets.setdefault(Bucket, {})
        return {}

    # Envoi d'un fichier local ; ExtraArgs peut contenir les métadonnées
    def upload_file(self, Filename: str, Bucket: str, Key: str, ExtraArgs: dict | None = None) -> None:
        """Enregistre l'objet Key avec la taille du fichier et ses métadonnées."""
        metadata = dict((ExtraArgs or {}).get("Metadata", {}))
        self.buckets[Bucket][Key] = {"Size": Path(Filename).stat().st_size, "Metadata": metadata}

    # Raccourci des exemples : un objet vide, sans fichier local
    def put(self, Bucket: str, Key: str) -> None:
        """Dépose un objet vide sous la clé Key."""
        self.buckets[Bucket][Key] = {"Size": 0, "Metadata": {}}

    # Comme boto3 : pas de clé « Contents » quand aucun objet ne correspond
    def list_objects_v2(self, Bucket: str, Prefix: str = "") -> dict:
        """Liste les objets dont la clé commence par Prefix, triés par clé."""
        contents = [{"Key": k, "Size": v["Size"]} for k, v in sorted(self.buckets[Bucket].items())
                    if k.startswith(Prefix)]
        return {"Contents": contents} if contents else {}

    # Métadonnées d'un objet
    def head_object(self, Bucket: str, Key: str) -> dict:
        """Renvoie {"Metadata": {…}} pour l'objet Key."""
        return {"Metadata": self.buckets[Bucket][Key]["Metadata"]}

    # Suppression, sans erreur si l'objet n'existe pas, comme S3
    def delete_object(self, Bucket: str, Key: str) -> dict:
        """Supprime l'objet Key."""
        self.buckets[Bucket].pop(Key, None)
        return {}


# Exception métier : main() l'attrape pour afficher un message clair et renvoyer le code 2
class BackupError(Exception):
    """Sauvegarde impossible : dossier introuvable ou erreur S3 (lab 4.4)."""


# Le même code parle à MinIO (au labo) ou à AWS (en production) : seule l'adresse change
def s3_client():
    """Crée un client S3 : MinIO si S3_ENDPOINT_URL est définie, sinon AWS (lab 4.4).

    Les identifiants ne sont jamais passés ici : boto3 les lit lui-même dans AWS_ACCESS_KEY_ID et
    AWS_SECRET_ACCESS_KEY.

    Renvoie :
        Un client boto3 « s3 ».
    """
    # Import ici : boto3 n'est installé qu'au lab 4.4
    import boto3

    # Adresse de MinIO, ou None pour AWS ; « or None » transforme une variable vide en None
    endpoint = os.environ.get("S3_ENDPOINT_URL") or None
    # Région : us-east-1 pour MinIO, Paris (eu-west-3) pour AWS, sauf si AWS_DEFAULT_REGION est définie
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1" if endpoint else "eu-west-3")
    return boto3.client("s3", endpoint_url=endpoint, region_name=region)


# dest_dir est le dossier où l'archive est créée, le dossier courant par défaut
def make_archive(folder: str | Path, dest_dir: str | Path = ".") -> Path:
    """Compresse un dossier en backup-AAAAMMJJ-HHMMSS.tar.gz (lab 4.4).

    Paramètres :
        folder : dossier à sauvegarder.
        dest_dir : dossier où créer l'archive.

    Renvoie :
        Le chemin de l'archive créée.

    Lève :
        BackupError : le dossier n'existe pas.

    Exemples (dossiers temporaires) :
        >>> import tempfile
        >>> src = Path(tempfile.mkdtemp()) / "config"
        >>> src.mkdir()
        >>> _ = (src / "app.conf").write_text("port=8080\\n")
        >>> archive = make_archive(src, dest_dir=tempfile.mkdtemp())
        >>> len(archive.name) == len("backup-AAAAMMJJ-HHMMSS.tar.gz") and archive.name.startswith("backup-2")
        True
        >>> with tarfile.open(archive) as tar:
        ...     tar.getnames()
        ['config', 'config/app.conf']
        >>> try:
        ...     make_archive("dossier-absent")
        ... except BackupError as exc:
        ...     print(exc)
        Dossier introuvable : dossier-absent
    """
    # Path, quel que soit le type reçu
    folder = Path(folder)
    # Dossier absent : erreur claire, avant de créer quoi que ce soit
    if not folder.is_dir():
        raise BackupError(f"Dossier introuvable : {folder}")
    name = f"backup-{datetime.now():%Y%m%d-%H%M%S}.tar.gz"
    # Chemin complet de l'archive
    archive = Path(dest_dir) / name
    # « w:gz » : écriture, compressée avec gzip ; le bloc with ferme l'archive
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(folder, arcname=folder.name)
    # Chemin de l'archive créée
    return archive


# Empreinte d'un fichier, calculée par blocs : la mémoire reste faible, même pour une archive de 10 Go
def sha256(path: Path) -> str:
    """Calcule l'empreinte SHA-256 d'un fichier, en hexadécimal (lab 4.4).

    Exemple (un fichier qui contient « abc ») :
        >>> import tempfile
        >>> p = Path(tempfile.mkdtemp()) / "abc.txt"
        >>> _ = p.write_bytes(b"abc")
        >>> sha256(p)
        'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    """
    # Calculateur d'empreinte, nourri bloc par bloc
    digest = hashlib.sha256()
    # « rb » : lecture en octets, sans décodage
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            # Le bloc nourrit le calcul
            digest.update(chunk)
    # Empreinte en hexadécimal : 64 caractères
    return digest.hexdigest()


# Création à la demande : la première sauvegarde crée le bucket
def ensure_bucket(client, bucket: str) -> None:
    """Crée le bucket s'il n'existe pas encore (lab 4.4, déjà complet).

    Hors de la région us-east-1, AWS exige la région du bucket à sa création
    (sinon : IllegalLocationConstraintException).
    """
    # Import ici : botocore est installé avec boto3, au lab 4.4
    from botocore.exceptions import ClientError

    # head_bucket réussit si le bucket existe et nous est accessible
    try:
        client.head_bucket(Bucket=bucket)
    # Bucket absent : on le crée
    except ClientError:
        # Trace de la création
        log.info("Création du bucket %s", bucket)
        # Région du client
        region = client.meta.region_name
        # Hors us-east-1 : la région doit être précisée
        if region and region != "us-east-1":
            client.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": region})
        # us-east-1 (et MinIO) : pas de configuration
        else:
            client.create_bucket(Bucket=bucket)


# prefix range les sauvegardes « dans » backups/ : en S3, ce n'est qu'un début de clé
def upload(client, archive: Path, bucket: str, prefix: str = "backups/") -> str:
    """Envoie l'archive dans le bucket, avec son empreinte SHA-256 en métadonnée (lab 4.4).

    Renvoie :
        La clé de l'objet créé, par exemple « backups/backup-20261126-140744.tar.gz ».
    """
    # Clé de l'objet : préfixe et nom de l'archive
    key = prefix + archive.name
    client.upload_file(str(archive), bucket, key, ExtraArgs={"Metadata": {"sha256": sha256(archive)}})
    # Clé de l'objet envoyé
    return key


# Le nom des sauvegardes contient leur date : trier par clé, c'est trier par date
def list_backups(client, bucket: str, prefix: str = "backups/") -> list[dict]:
    """Liste les sauvegardes du bucket, de la plus ancienne à la plus récente (lab 4.4, déjà complet).

    Renvoie :
        [{"key": clé, "size": taille en octets}, …].
    """
    # Objets dont la clé commence par prefix
    response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    # « Contents » est absent quand aucun objet ne correspond
    objects = [{"key": o["Key"], "size": o["Size"]} for o in response.get("Contents", [])]
    # Tri chronologique, grâce à l'horodatage dans le nom
    return sorted(objects, key=lambda o: o["key"])


# keep vaut 5 par défaut : les 5 sauvegardes les plus récentes sont gardées
def rotate(client, bucket: str, keep: int = 5, prefix: str = "backups/") -> list[str]:
    """Supprime les sauvegardes les plus anciennes au-delà de keep (lab 4.4).

    Paramètres :
        client : client S3 (boto3, ou MemoryS3 dans les exemples).
        bucket : nom du bucket.
        keep : nombre de sauvegardes à garder ; 0 ou moins pour ne rien supprimer.

    Renvoie :
        Les clés supprimées, de la plus ancienne à la plus récente.

    Exemples (faux stockage en mémoire, 7 sauvegardes du 20 au 26 novembre) :
        >>> s3 = MemoryS3(buckets=("b",))
        >>> for day in range(20, 27):
        ...     s3.put("b", f"backups/backup-202611{day}-120000.tar.gz")
        >>> rotate(s3, "b", keep=5)
        ['backups/backup-20261120-120000.tar.gz', 'backups/backup-20261121-120000.tar.gz']
        >>> [o["key"][15:23] for o in list_backups(s3, "b")]
        ['20261122', '20261123', '20261124', '20261125', '20261126']
        >>> rotate(s3, "b", keep=5), rotate(s3, "b", keep=10)
        ([], [])
    """
    # Sauvegardes existantes, de la plus ancienne à la plus récente
    backups = list_backups(client, bucket, prefix)
    old: list[str] = [o["key"] for o in backups[:-keep]] if keep > 0 else []
    # Suppression de chaque ancienne sauvegarde
    for key in old:
        client.delete_object(Bucket=bucket, Key=key)
    # Clés supprimées
    return old


# client vaut None par défaut : le vrai client S3 ; les exemples passent un MemoryS3
def backup(folder: str | Path, bucket: str, keep: int = 5, client=None, dest_dir: str | Path = ".") -> dict:
    """Archive un dossier, l'envoie dans le bucket, puis applique la rotation (lab 4.4).

    L'archive locale est supprimée dans tous les cas, que l'envoi réussisse ou non.

    Paramètres :
        folder : dossier à sauvegarder.
        bucket : bucket de destination, créé s'il n'existe pas.
        keep : nombre de sauvegardes à garder.
        client : client S3 ; None (défaut) pour s3_client().
        dest_dir : dossier où l'archive est créée le temps de l'envoi.

    Renvoie :
        {"uploaded": clé envoyée, "deleted": clés supprimées par la rotation}.

    Lève :
        BackupError : dossier introuvable, ou erreur S3 (identifiants, MinIO injoignable…).

    Exemple (faux stockage en mémoire, sans bucket au départ) :
        >>> import tempfile
        >>> work = Path(tempfile.mkdtemp())
        >>> (work / "config").mkdir()
        >>> _ = (work / "config" / "app.conf").write_text("port=8080\\n")
        >>> s3 = MemoryS3()
        >>> result = backup(work / "config", "cloudnova-backups", client=s3, dest_dir=work)
        >>> result["uploaded"].startswith("backups/backup-"), result["deleted"]
        (True, [])
        >>> metadata = s3.head_object(Bucket="cloudnova-backups", Key=result["uploaded"])["Metadata"]
        >>> len(metadata.get("sha256", ""))
        64
        >>> sorted(p.name for p in work.iterdir())
        ['config']
    """
    # Import ici : botocore est installé avec boto3, au lab 4.4
    from botocore.exceptions import BotoCoreError, ClientError

    # Vrai client S3, sauf si on en fournit un
    client = client or s3_client()
    # Archive locale ; BackupError si le dossier n'existe pas
    archive = make_archive(folder, dest_dir)
    # Bloc surveillé : les erreurs S3 deviennent des BackupError
    try:
        # Bucket créé si besoin, archive envoyée, anciennes sauvegardes supprimées
        ensure_bucket(client, bucket)
        key = upload(client, archive, bucket)
        deleted = rotate(client, bucket, keep)
    # BotoCoreError : identifiants absents, MinIO injoignable… ; ClientError : refus du service
    except (BotoCoreError, ClientError) as exc:
        raise BackupError(f"Échec S3 : {exc}") from exc
    # Exécuté dans tous les cas, succès ou erreur
    finally:
        archive.unlink(missing_ok=True)
    # Bilan de la sauvegarde
    return {"uploaded": key, "deleted": deleted}
