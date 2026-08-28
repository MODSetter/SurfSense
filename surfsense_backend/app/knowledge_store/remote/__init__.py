"""Workspace git remotes: destinations the local engine can push to.

Deliberately re-exports nothing. :mod:`.facade` and :mod:`.forges` talk to git
hosts, while :mod:`.queue` is a writer's last step and must stay cheap to
import; a convenience re-export here would put the former on the latter's
import path.

* :mod:`.facade` — ``WorkspaceRemotes``: add / remove / list remotes on a workspace
* :mod:`.queue` — ``enqueue_push``
* :mod:`.schemas` — spec, status, credentials
* :mod:`.persistence` — workspace columns
* :mod:`.forges` — ``RemoteProvider`` per host
* :mod:`.api` — HTTP adapter
"""
