from collections import OrderedDict

try:
    from collections.abc import Mapping, Sequence
except ImportError:
    from collections import Mapping, Sequence
    
import json

COMPACT_SEPARATORS = (',', ':')

def order_by_key(kv):
  key, val = kv
  return key

def recursive_order(node):
  if isinstance(node, Mapping):
    ordered_mapping = OrderedDict(sorted(node.items(), key=order_by_key))
    for key, value in ordered_mapping.items():
      ordered_mapping[key] = recursive_order(value)
    return ordered_mapping
  elif isinstance(node, Sequence) and not isinstance(node, (str, bytes)):
    return [recursive_order(item) for item in node]
  return node

def stringify(node):
  return json.dumps(recursive_order(node), separators=COMPACT_SEPARATORS)