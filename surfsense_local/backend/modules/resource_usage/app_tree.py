"""Which processes are the app's, and which child of the shell started each."""

from collections import defaultdict
from collections.abc import Callable, Mapping


def branches(
    parents: Mapping[int, int],
    root: int,
    born: Callable[[int], float | None],
) -> dict[int, int]:
    """Every descendant of `root` mapped to the child of `root` above it.

    `born` is a create time, or None once the process is gone. A process older
    than its listed parent is a stranger: Windows keeps a dead parent's pid as
    the ppid, and that pid can since belong to one of ours.
    """
    children: defaultdict[int, list[int]] = defaultdict(list)
    for pid, parent in parents.items():
        if pid != parent:
            children[parent].append(pid)

    tree = {root: root}
    stack: list[tuple[int, int, int | None]] = [
        (child, root, None) for child in children[root]
    ]
    while stack:
        pid, parent, branch = stack.pop()
        if pid in tree:
            continue
        parent_born, pid_born = born(parent), born(pid)
        if parent_born is None or pid_born is None or pid_born < parent_born:
            continue
        branch = pid if branch is None else branch
        tree[pid] = branch
        stack.extend((child, pid, branch) for child in children[pid])
    return tree
