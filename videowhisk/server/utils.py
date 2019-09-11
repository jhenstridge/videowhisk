import asyncio
import logging
import operator

log = logging.getLogger(__name__)

async def cancel_task(task):
    """Cancel an asyncio task.

    If the task raises any excpetion other than CancelledError, the
    exception will be logged.
    """
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("Task %r failed", task)


def forward_prop(dest_prop):
    assert '.' in dest_prop
    parent, prop_name = dest_prop.rsplit('.', 1)

    getter = operator.attrgetter(dest_prop)
    parent_getter = operator.attrgetter(parent)
    def setter(object, value):
        setattr(parent_getter(object), prop_name, value)
    return property(getter, setter)
