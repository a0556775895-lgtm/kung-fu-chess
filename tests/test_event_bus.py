from dataclasses import dataclass

from bus.event_bus import EventBus


@dataclass(frozen=True)
class FirstEvent:
    value: int


@dataclass(frozen=True)
class SecondEvent:
    value: int


def test_publish_calls_handlers_in_subscription_order():
    bus = EventBus()
    calls = []

    bus.subscribe(FirstEvent, lambda event: calls.append(("first", event.value)))
    bus.subscribe(FirstEvent, lambda event: calls.append(("second", event.value)))

    bus.publish(FirstEvent(7))

    assert calls == [("first", 7), ("second", 7)]


def test_event_types_are_isolated():
    bus = EventBus()
    calls = []

    bus.subscribe(FirstEvent, lambda event: calls.append(("first", event.value)))
    bus.subscribe(SecondEvent, lambda event: calls.append(("second", event.value)))

    bus.publish(FirstEvent(3))

    assert calls == [("first", 3)]


def test_subscribe_returns_idempotent_unsubscribe_function():
    bus = EventBus()
    calls = []
    cancel = bus.subscribe(FirstEvent, lambda event: calls.append(event.value))

    cancel()
    cancel()
    bus.publish(FirstEvent(1))

    assert calls == []


def test_explicit_unsubscribe_removes_handler():
    bus = EventBus()
    calls = []

    def handler(event):
        calls.append(event.value)

    bus.subscribe(FirstEvent, handler)
    bus.unsubscribe(FirstEvent, handler)
    bus.publish(FirstEvent(2))

    assert calls == []


def test_cancel_only_removes_its_own_duplicate_subscription():
    bus = EventBus()
    calls = []

    def handler(event):
        calls.append(event.value)

    cancel_first = bus.subscribe(FirstEvent, handler)
    bus.subscribe(FirstEvent, handler)

    cancel_first()
    cancel_first()
    bus.publish(FirstEvent(6))

    assert calls == [6]


def test_handler_can_unsubscribe_itself_during_publish():
    bus = EventBus()
    calls = []
    cancel = None

    def handler(event):
        calls.append(event.value)
        cancel()

    cancel = bus.subscribe(FirstEvent, handler)

    bus.publish(FirstEvent(4))
    bus.publish(FirstEvent(5))

    assert calls == [4]


def test_publish_without_subscribers_is_a_no_op():
    bus = EventBus()

    bus.publish(FirstEvent(9))
