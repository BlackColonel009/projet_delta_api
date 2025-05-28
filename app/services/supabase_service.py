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
    if res.get("error"):
        raise Exception(f"Erreur upload Supabase: {res['error']['message']}")

    # Génère URL publique
    public_url = supabase.storage.from_(bucket).get_public_url(filename)
    return public_url


def delete_from_supabase(filename: str, bucket: str = BUCKET_NAME):
    """
    Supprime un fichier du bucket Supabase
    """
    res = supabase.storage.from_(bucket).remove([filename])
    if res.get("error"):
        raise Exception(f"Erreur suppression Supabase: {res['error']['message']}")
