"""Pure, side-effect-free presentation logic for notifications.

Handlers compute their user-facing title/message/status/metadata here, then
persist the result. Keeping this layer free of I/O makes it unit-testable
without a database.
"""
