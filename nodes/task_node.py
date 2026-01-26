import logging
from datetime import datetime, timezone, timedelta

from tools.trello_tool import create_trello_card, get_existing_cards
from workflow.state import WorkflowState

logger = logging.getLogger(__name__)


def _find_next_available_date(existing_cards: list[dict], max_days: int = 30) -> str:
    """
    Find the first date with fewer than 5 tasks.
    
    Args:
        existing_cards: List of Trello cards with 'due' field
        max_days: Maximum days to search ahead (default 30)
    
    Returns:
        ISO datetime string for 23:59:59 UTC on the first available date
    """
    search_date = datetime.now(timezone.utc).date()
    
    for day_offset in range(max_days):
        check_date = search_date + timedelta(days=day_offset)
        date_str = check_date.isoformat()
        
        # Count tasks on this date
        tasks_on_date = sum(
            1 for c in existing_cards
            if (c.get("due") or "") and str(c.get("due", "")).startswith(date_str)
        )
        
        if tasks_on_date < 5:
            # Return datetime at 23:59:59 UTC for this date
            return check_date.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
    
    # Fallback: schedule 30 days from now
    fallback_date = search_date + timedelta(days=30)
    return fallback_date.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()


class TaskNode:
    """Creates a Trello card for emails classified as tasks or assessments."""

    @staticmethod
    def execute(state: WorkflowState) -> WorkflowState:
        """Task graph node — creates a Trello card with duplicate and daily-limit guards."""
        try:
            extracted = state.get("extracted_data")
            classification = state.get("classification")
            email = state["email_data"]

            role = getattr(extracted, "role", None) or email.subject or "Unknown Role"
            company = getattr(extracted, "company", None)  # Leave as None if not extracted
            deadline = getattr(extracted, "deadline", None)
            category = classification.category.value if classification else "task"
            priority = classification.priority.value if classification else "medium"

            # Build card name — include company only if present
            company_part = f" @ {company}" if company else ""
            name = f"[{category.upper()}] {role}{company_part}"
            
            task_description = getattr(extracted, "task_description", None)
            estimated_time = getattr(extracted, "estimated_time", None)
            dependencies = getattr(extracted, "dependencies", None)

            desc = (
                f"Source Email: {email.subject}\n"
                f"From: {email.sender}\n"
                f"Role: {role}\n"
                f"Company: {company or 'Not specified'}\n"
                f"Deadline: {deadline or 'Not specified'}\n"
                f"Priority: {priority}\n"
                + (f"Description: {task_description}\n" if task_description else "")
                + (f"Estimated Time: {estimated_time}\n" if estimated_time else "")
                + (f"Dependencies: {dependencies}\n" if dependencies else "")
            )
            due = deadline or datetime.now(timezone.utc).replace(
                hour=23, minute=59, second=59, microsecond=0
            ).isoformat()

            existing_cards = get_existing_cards()

            if any(card["name"] == name for card in existing_cards):
                logger.info("Duplicate Trello card skipped: %s", name)
                return {**state, "task_created": False, "task_reason": "duplicate", "action_failed": False}

            # Check daily limit with priority awareness
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            today_cards = [
                c for c in existing_cards 
                if (c.get("due") or "") and str(c.get("due", "")).startswith(today_str)
            ]
            
            # If daily limit reached: HIGH priority allows override, others reschedule to next available date
            if len(today_cards) >= 5:
                if priority == "high":
                    logger.info("Daily limit reached but HIGH priority — allowing task creation today")
                    # Keep due as-is for today
                else:
                    # Find next available date with < 5 tasks
                    next_available_due = _find_next_available_date(existing_cards)
                    logger.info("Daily limit reached. Rescheduling %s from %s to %s", name, today_str, next_available_due[:10])
                    due = next_available_due

            card = create_trello_card(name=name, desc=desc, due=due)
            if card:
                logger.info("Trello card created: %s", card["url"])
                return {**state, "task_created": True, "task_url": card["url"], "action_failed": False, "execution_result": "SUCCESS"}

            return {**state, "task_created": False, "task_reason": "api_error", "action_failed": True}

        except Exception as e:
            logger.exception("TaskNode failed: %s", str(e))
            return {**state, "action_failed": True, "action_error": str(e)}
