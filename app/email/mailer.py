from fastapi_mail import FastMail, MessageSchema, MessageType
from io import BytesIO

async def send_facture_email(client_email: str, pdf_buffer: BytesIO, facture_id: int):
    message = MessageSchema(
        subject=f"Facture #{facture_id}",
        recipients=[client_email],
        body=f"Veuillez trouver ci-joint la facture #{facture_id}. Merci pour votre confiance.",
        subtype=MessageType.plain,
        attachments=[("facture.pdf", pdf_buffer.getvalue(), "application/pdf")]
    )
    fm = FastMail(conf)
    await fm.send_message(message)
