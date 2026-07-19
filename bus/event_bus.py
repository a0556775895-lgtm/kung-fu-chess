"""Generic in-process publish/subscribe channel.

Knows nothing about any specific event type — callers register handlers
per event class and publish instances of that class.
"""

from collections import defaultdict


class EventBus:
    def __init__(self):
        """Start with no subscribers for any event type."""
        self._handlers = defaultdict(list)

    def subscribe(self, event_type, handler) -> None:
        """Register handler to be called with every future event of event_type."""
        self._handlers[event_type].append(handler)

    def publish(self, event) -> None:
        """Call every handler subscribed to type(event), in registration order."""
        for handler in self._handlers[type(event)]:
            handler(event)
