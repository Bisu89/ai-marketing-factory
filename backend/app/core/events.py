import logging
import threading
from collections import defaultdict
from collections.abc import Callable

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict], None]


class EventBus:
    """In-process pub/sub so the core domain (downloads, videos) never has to
    import a future module directly to notify it of something.

    Publishers own no knowledge of subscribers. A future module (Subtitle
    Generator, Story Generator, ...) subscribes to the events it cares about
    at startup; if no one has subscribed, publish() is a no-op. Handlers run
    synchronously, in the caller's thread -- a slow handler should hand off
    to its own background queue rather than block the publisher.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        with self._lock:
            self._handlers[event_name].append(handler)

    def publish(self, event_name: str, payload: dict) -> None:
        with self._lock:
            handlers = list(self._handlers.get(event_name, ()))

        for handler in handlers:
            try:
                handler(payload)
            except Exception:
                logger.exception("Event handler for '%s' raised", event_name)
