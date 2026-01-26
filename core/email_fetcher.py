from datetime import datetime
from email.header import decode_header

import imapclient
import email
from config.settings import settings
from schema.email_dto import AttachmentDTO, EmailDTO
from core.imap_connector import IMAPConnector
class EmailFetcher:
    """
    EmailFetcher is responsible for connecting to the IMAP server, fetching email data, and parsing it into a structured format (EmailDTO).
    """  
    def fetch_email(self,uid):
        """
        Fetch an email by its UID from the IMAP server and parse it into an EmailDTO.
        :param uid: The UID of the email to fetch
        :return: An EmailDTO object containing the parsed email data
        """
        imap_connector = IMAPConnector(settings.IMAP_SERVER, settings.EMAIL_USER_NAME, settings.EMAIL_PASSWORD)
        conn = imap_connector.connect()
        conn.select_folder("INBOX")
        raw = conn.fetch([uid], ['RFC822'])[uid][b'RFC822']
        message = email.message_from_bytes(raw)
        email_dto = self._parse_email(message, uid)
        imap_connector.disconnect(conn)
        return email_dto

    def _mime_header(self, value):
        """
        Decode MIME-encoded email headers.
        
        :param value: The MIME-encoded header value
        :return: The decoded header value
        """
        decoded_parts = decode_header(value)
        decoded_string = []
        for part,encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_string.append(part.decode(encoding or 'utf-8', errors='ignore'))
            else:
                decoded_string.append(part)
        return ''.join(decoded_string)

    def _parse_email(self,email_message, uid) -> EmailDTO:
        """
        Parse an email message into an EmailDTO.
        
        :param email_message: The raw email message
        :param uid: The UID of the email
        :return: An EmailDTO object containing parsed email data
        """
        body_text = None
        body_html = None
        attachments = []

        for part in email_message.walk():
            if part.is_multipart():
                continue
            content_type = part.get_content_type()
            content_disposition = part.get("Content-Disposition", "")
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            if content_type == 'text/plain':
                body_text = payload.decode(errors='ignore')
            elif content_type == 'text/html':
                body_html = payload.decode(errors='ignore')
            elif 'attachment' in content_disposition:
                filename = part.get_filename()
                attachments.append(AttachmentDTO(
                    filename=filename, content=payload,content_type=content_type))
                
        msg_id = self._mime_header(email_message.get('Message-ID', ''))
        if not msg_id or not isinstance(msg_id, str):
            msg_id = f"{uid}@unknown"
        
        email_dto = EmailDTO(
            uid=uid,
            message_id=msg_id,
            subject=self._mime_header(email_message.get('Subject', '')),
            sender=self._mime_header(email_message.get('From', '')),
            recipients= [self._mime_header(addr) for addr in email_message.get_all('To',[])],
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
            received_at=email.utils.parsedate_to_datetime(email_message.get('Date')) if email_message.get('Date') else None
        )
        return email_dto