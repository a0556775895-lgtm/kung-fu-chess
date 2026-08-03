"""Generic in-process publish/subscribe channel.

Knows nothing about any specific event type — callers register handlers
per event class and publish instances of that class.
"""

from collections import defaultdict


class EventBus:
    def __init__(self):
        """Start with no subscribers for any event type."""
        self._handlers = defaultdict(list)

    def subscribe(self, event_type, handler):
        """Register a handler and return a function that cancels this subscription."""
        self._handlers[event_type].append(handler)
        is_active = True

        def unsubscribe() -> None:
            nonlocal is_active
            if not is_active:
                return
            self.unsubscribe(event_type, handler)
            is_active = False

        return unsubscribe

    def unsubscribe(self, event_type, handler) -> None:
        """Remove one matching subscription; do nothing if it is already absent."""
        handlers = self._handlers.get(event_type)
        if not handlers:
            return

        try:
            handlers.remove(handler)
        except ValueError:
            return

        if not handlers:
            del self._handlers[event_type]

    def publish(self, event) -> None:
        """Call every handler subscribed to type(event), in registration order."""
        for handler in list(self._handlers.get(type(event), ())):
            handler(event)
