import json
import re

from celery import Celery
import redis
from sympy import symbols
from config.settings import settings
from schema.DecisionType import DecisionType
from schema.OutputClassifer import ClassificationResult
from schema.mail_extractor import ExtractionResult
from schema.email_dto import EmailDTO
from schema.planning_type import PlanningEvent
from workflow.graph import WorkflowGraph
from workflow.state import WorkflowState
import time
from core.email_fetcher import EmailFetcher
from core.database import Database
from celery.signals import task_failure

from fastapi import FastAPI,Response,Request
from twilio.twiml.messaging_response import MessagingResponse

email_obj = EmailFetcher()
db_obj = Database()
celery_app = Celery('tasks', broker=settings.CELERY_BROKER_URL)
GRAPH = WorkflowGraph.create()

app = FastAPI()


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None,**kwargs):
    print(f"Task failed: {task_id}, Exception: {exception}")


def _persist_workflow_status(message_id: str, result_state: WorkflowState):
    if result_state["decision"] == DecisionType.REVIEW:
        db_obj.mark_review_needed(message_id)
        return

    if result_state["decision"] == DecisionType.REJECT:
        db_obj.mark_ignored(message_id)
        return

    if result_state.get("execution_result") == "SUCCESS":
        db_obj.mark_success(message_id)
        return

    db_obj.mark_failed(message_id)

@celery_app.task(bind=True, max_retries=3)
def execute_workflow_task(self, uid):
    email_data = None
    try:
        email_data = email_obj.fetch_email(uid)

        if not db_obj.try_claim_email(email_data.message_id):
            return

        state = WorkflowState(email_data=email_data)
        result_state = GRAPH.invoke(state)
        _persist_workflow_status(email_data.message_id, result_state)

    except Exception as exc:
        if email_data:
            db_obj.mark_failed(email_data.message_id)
        raise self.retry(exc=exc, countdown=5)

@app.route("/whatsapp_hook", methods=["POST"])
async def whatsapp_webhook(request: Request):
    state_db = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=2, decode_responses=True)
    resp = MessagingResponse()

    form_data = await request.form()
    incoming_text = form_data.get("Body", "").strip()    
    match = re.search(r"(APPROVE|REJECT)\s+(\S+)", incoming_text, re.IGNORECASE)
    
    if match:
        action = match.group(1).upper()
        ref_id = match.group(2).strip()
        
        val = state_db.get(f"state:{ref_id}") 
        
        if val:
            state = json.loads(val)
            whatsapp_processing_task.delay(state, action)
            resp.message(f"Processing your {action} request for ID: {ref_id}...")
        else:
            resp.message(f"Error: Request {ref_id} not found or expired.")
    else:
        resp.message("Invalid format. Please reply with: APPROVE <ID> or REJECT <ID>")
    
    return Response(content=str(resp), media_type="application/xml")

@celery_app.task(name="whatsapp_processing_task", bind=True)
def whatsapp_processing_task(self, state, action):
    """
    action: will be 'APPROVE' or 'REJECT' passed from the webhook
    """
    state["email_data"] = EmailDTO.model_validate(state["email_data"])
    state["classification"] = ClassificationResult.model_validate(state["classification"])
    state["extracted_data"] = ExtractionResult.model_validate(state["extracted_data"]) if state.get("extracted_data") else None
    state["plan_type"] = PlanningEvent(state["plan_type"]) if state.get("plan_type") else None

    state["event_type"] = "APPROVED" if action == "APPROVE" else "REJECTED"
    state["decision"] = (
        DecisionType.AUTO_EXECUTE if action == "APPROVE" else DecisionType.REJECT
    )   
    try:
        result_state = GRAPH.invoke(state)
        _persist_workflow_status(state["email_data"].message_id, result_state)
        print(f"Workflow resumed with event: {state['event_type']}")
    except Exception as e:
        db_obj.mark_failed(state["email_data"].message_id)
        print(f"Graph execution failed: {e}")
