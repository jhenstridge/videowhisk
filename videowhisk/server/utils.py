import logging
import operator

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


def forward_prop(dest_prop):
    assert '.' in dest_prop
    parent, prop_name = dest_prop.rsplit('.', 1)

    getter = operator.attrgetter(dest_prop)
    parent_getter = operator.attrgetter(parent)
    def setter(object, value):
        setattr(parent_getter(object), prop_name, value)
    return property(getter, setter)
