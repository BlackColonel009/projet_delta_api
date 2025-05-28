import os
from supabase import create_client, Client
from dotenv import load_dotenv
from uuid import uuid4

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

BUCKET_NAME = "avatars"


def upload_to_supabase(file, filename: str, bucket: str = BUCKET_NAME) -> str:
    """
    Upload un fichier dans Supabase Storage et retourne l'URL publique
    """
    file_bytes = file.file.read()

    # Upload
    res = supabase.storage.from_(bucket).upload(f"{filename}", file_bytes, {"content-type": file.content_type})

    # Si l'upload échoue, la méthode `upload` lèvera une exception. Donc tu peux logguer ou ignorer.
    # Pour être sûr, convertis la réponse si besoin :
    if isinstance(res, dict) and res.get("error"):
        raise Exception(f"Upload failed: {res.get('message')}")

    # Génère URL publique
    public_url = supabase.storage.from_(bucket).get_public_url(filename)
    return public_url


def delete_from_supabase(file_url: str):
    """
    Supprime un fichier Supabase à partir de son URL publique
    """
    from urllib.parse import urlparse

    parsed_url = urlparse(file_url)
    path = parsed_url.path  # /storage/v1/object/public/avatars/nom-fichier.jpg
    parts = path.split("/")

    try:
        bucket = parts[4]  # "avatars"
        filename = "/".join(parts[5:])  # "nom-fichier.jpg"
    except IndexError:
        raise ValueError("URL Supabase invalide")

    res = supabase.storage.from_(bucket).remove([filename])
    return res
