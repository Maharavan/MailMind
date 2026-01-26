import email
import logging
import imapclient
import socket
from config.settings import settings
from core.task_scheduler import execute_workflow_task
from core.imap_connector import IMAPConnector

class IMAPListener:
    def __init__(self):
        self.conn = None
        self._running = True

    def start(self):
        while self._running:             
            try:
                imap_connector = IMAPConnector(settings.IMAP_SERVER, settings.EMAIL_USER_NAME, settings.EMAIL_PASSWORD)
                self.conn = imap_connector.connect()
                logging.info("Connected to IMAP server.")
                self._idle_loop()
            except KeyboardInterrupt:
                logging.info("Shutting down...")
                self._running = False
            except (imapclient.exceptions.IMAPClientError, socket.error) as e:
                logging.error("Connection lost, reconnecting: %s", e)
            except Exception as e:
                logging.error("Unexpected error: %s", e)
            finally:
                if self.conn:
                    self.conn.logout()

    def _idle_loop(self):
        self.conn.select_folder('INBOX')
        logging.info("Listening for new emails...")
        iteration = 1
        
        while self._running:
            try:
                self.conn.idle()
                logging.info("Iteration %s: IDLE mode active.", iteration)
                
                responses = self.conn.idle_check(timeout=120)
                
                self.conn.idle_done()
                
                if responses:
                    logging.info("Server activity: %s", responses)
                    if any(r[1] in (b'EXISTS', b'RECENT') for r in responses):
                        self._process_new_emails()
                else:
                    logging.info("No new emails (Heartbeat).")
                
                iteration += 1
            except Exception as e:
                logging.error("Error in IDLE loop: %s", e)
                raise

    def _process_new_emails(self):
        """
        Fetch UIDs for truly unseen emails and dispatch tasks.
        """
        uids = self.conn.search(['UNSEEN'])

        if not uids:
            return

        uids = sorted(uids, reverse=True)[:5]
        logging.info("Processing UIDs: %s", uids)

        for uid in uids:
            res = execute_workflow_task.delay(uid)
            if res.state == 'FAILURE':
                logging.error("Failed to dispatch task for UID %s: %s", uid, res.get(traceback=True))