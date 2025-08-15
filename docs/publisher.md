# Publisher Queue

The publisher module offers a minimal in-process pub/sub mechanism built on
top of Python's ``asyncio.Queue``.  It is intended for decoupling components in
lightweight deployments where an external message broker would be overkill.

## Usage

```python
from solbot.service import publisher

# optional: configure queue limits and overflow behaviour
publisher.configure(maxsize=100, overflow="drop_oldest")

# subscribers receive their own queue
events = publisher.subscribe()

# publishers send dictionaries (or any object)
publisher.publish({"event": "example"})

# consumers await messages
msg = await events.get()
```

## Configuration

``configure`` accepts two optional parameters:

* ``maxsize`` – maximum items queued per subscriber. ``0`` (default) means
  unbounded.
* ``overflow`` – strategy when a subscriber queue is full:
  * ``"drop_new"`` – discard the new message for that subscriber (default).
  * ``"drop_oldest"`` – remove the oldest message and enqueue the new one.
  * ``"raise"`` – propagate :class:`asyncio.QueueFull`.

These values can also be supplied when constructing the API server via
``create_app`` using ``publisher_queue_size`` and ``publisher_overflow``.

