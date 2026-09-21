"""How the probe child reports a device to its parent.

One line per device, tab separated, because the child is a separate process and
its stdout is shared with whatever ggml decides to log on the way past. A format
this plain survives a stray log line: an unparseable one is skipped rather than
taking the listing with it.
"""

from modules.llm.hardware.devices import Device, DeviceType

_FIELDS = 5
_SEPARATOR = "\t"


def encode_line(device: Device) -> str:
    """One device as one line.

    A description can carry anything a driver put in it, so the separator is
    replaced rather than escaped: the fields are read positionally and a space
    changes nothing a caller reads.
    """
    return _SEPARATOR.join(
        (
            _clean(device.name),
            _clean(device.description),
            str(int(device.type)),
            str(device.total_bytes),
            str(device.free_bytes),
        )
    )


def decode_lines(text: str) -> list[Device]:
    """Every device the child reported, skipping anything that is not one.

    ggml logs to stdout on some backends, so a line that does not parse is far
    more likely to be a log line than a device. Dropping it keeps the machine's
    real devices rather than refusing the whole listing over a stray one.
    """
    devices = []
    for line in text.splitlines():
        parts = line.split(_SEPARATOR)
        if len(parts) != _FIELDS:
            continue
        name, description, raw_type, total, free = parts
        try:
            device = Device(
                name=name,
                description=description,
                type=DeviceType.parse(int(raw_type)),
                total_bytes=int(total),
                free_bytes=int(free),
            )
        except ValueError:
            continue
        devices.append(device)
    return devices


def _clean(text: str) -> str:
    return text.replace(_SEPARATOR, " ").replace("\n", " ")
