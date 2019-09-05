import logging

log = logging.getLogger(__name__)

def cancel_task(task):
    """Cancel an asyncio task.

    If the task has already completed and raised an exception, log
    that exception.
    """
    if task.done():
        try:
            task.result()
        except Exception:
            log.exception("Task %r failed", task)
    else:
        task.cancel()
