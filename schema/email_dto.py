from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class AttachmentDTO(BaseModel):
    filename: Optional[str]
    content_type: str
    content: bytes


class EmailDTO(BaseModel):
    uid: int 
    message_id: Optional[str]
    subject: Optional[str]
    sender: Optional[str]
    recipients: Optional[List[str]]
    body_text: Optional[str]
    body_html: Optional[str]
    attachments: List[AttachmentDTO] = []
    received_at: Optional[datetime]