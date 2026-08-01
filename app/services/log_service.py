import logging
import queue
import time
import json
import itertools
_subscribers = []
_lock_counter = itertools.count()
MAX_QUEUE_SIZE = 500
class SSEHandler(logging.Handler):
    def emit(self, record):
        try:
            message = self.format(record)
        except Exception:
            message = record.getMessage()
        log_frontend(message, level=record.levelname.lower(), source=record.name)
def init_log_streaming(app):
    handler = SSEHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(handler)
def log_frontend(message, level="info", source="app"):
    event = {
        "id": next(_lock_counter),
        "ts": time.time(),
        "level": level,
        "source": source,
        "message": message,
    }
    for q in list(_subscribers):
        try:
            q.put_nowait(event)
        except queue.Full:
            pass
    return event
def subscribe():
    q = queue.Queue(maxsize=MAX_QUEUE_SIZE)
    _subscribers.append(q)
    return q
def unsubscribe(q):
    if q in _subscribers:
        _subscribers.remove(q)
def stream_events(q):
    yield "retry: 2000\n\n"
    while True:
        try:
            event = q.get(timeout=15)
            yield f"id: {event['id']}\ndata: {json.dumps(event)}\n\n"
        except queue.Empty:
            yield ": keep-alive\n\n"