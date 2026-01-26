import logging

import imapclient
import email
from email.header import decode_header


class IMAPConnector:
    """
    IMAPConnector is responsible for connecting to the IMAP server, fetching emails, and parsing them into EmailDTO objects.
    """
    def __init__(self, imap_server, email_user, email_password):
        self.imap_server = imap_server
        self.email_user = email_user
        self.email_password = email_password

    def connect(self):
        """
        Connect to the IMAP server and return the connection object.
        """
        conn = imapclient.IMAPClient(self.imap_server, ssl=True)
        conn.login(self.email_user, self.email_password)
        return conn
    
    def disconnect(self, conn):
        """
        Disconnect from the IMAP server.
        """
        if conn:
            conn.logout()
            logging.info("Disconnected from IMAP server")