import httpx
from app.config import settings

def send_whatsapp_message(numero: str, message: str):
    url = f"https://graph.facebook.com/v18.0/{settings.whatsapp_phone_number_id}/messages"

    headers = {
        "Authorization": f"Bearer {settings.whatsapp_token}",
        "Content-Type": "application/json"
    }

    data = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "text",
        "text": {"body": message}
    }

    response = httpx.post(url, headers=headers, json=data)

    if response.status_code == 200:
        print(f"✅ Message WhatsApp envoyé à {numero}")
    else:
        print(f"❌ Erreur envoi WhatsApp à {numero} : {response.status_code} - {response.text}")
