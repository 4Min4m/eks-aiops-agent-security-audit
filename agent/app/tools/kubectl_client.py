"""Read-only `kubectl describe pod` equivalent, via the Kubernetes Python
client rather than shelling out to a `kubectl` binary — one fewer thing to
install in the container image, and it's easier to guarantee read-only
behavior when you're calling a typed API method (`read_namespaced_pod`)
instead of exec-ing an arbitrary CLI.

Read-only is enforced at two layers, per the plan's Phase 0 safety
decision:
  1. Here: only `read_namespaced_pod` / `list_namespaced_event` are called —
     no `patch`, `delete`, or `exec` methods exist in this file at all.
  2. In agent/k8s/serviceaccount-rbac.yaml: the ServiceAccount's RBAC only
     grants get/list/watch verbs. Even a bug in this code couldn't mutate
     anything, because the API server itself would reject a write.
"""
from __future__ import annotations

from kubernetes import client, config


def _get_core_v1() -> client.CoreV1Api:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        # Fallback for local/Codespaces testing against a kubeconfig.
        config.load_kube_config()
    return client.CoreV1Api()


def describe_pod(namespace: str, pod: str) -> str:
    """Return a condensed, human-readable equivalent of
    `kubectl describe pod` for the given pod: status, container states,
    and recent Events — the fields actually useful for root-causing a
    CrashLoopBackOff, not the full raw object dump.
    """
    core = _get_core_v1()

    try:
        pod_obj = core.read_namespaced_pod(name=pod, namespace=namespace)
    except client.exceptions.ApiException as exc:
        return f"[failed to read pod {pod} in {namespace}: {exc.reason}]"

    lines = [f"Pod: {pod_obj.metadata.name}", f"Phase: {pod_obj.status.phase}"]

    for cs in pod_obj.status.container_statuses or []:
        lines.append(f"- container={cs.name} ready={cs.ready} restart_count={cs.restart_count}")
        if cs.state.waiting:
            lines.append(
                f"  waiting: reason={cs.state.waiting.reason} message={cs.state.waiting.message}"
            )
        if cs.state.terminated:
            lines.append(
                f"  last_terminated: reason={cs.state.terminated.reason} "
                f"exit_code={cs.state.terminated.exit_code}"
            )

    try:
        events = core.list_namespaced_event(
            namespace=namespace,
            field_selector=f"involvedObject.name={pod}",
        )
        lines.append("Recent events:")
        for ev in events.items[-10:]:
            lines.append(f"- [{ev.type}] {ev.reason}: {ev.message}")
    except client.exceptions.ApiException as exc:
        lines.append(f"[failed to list events: {exc.reason}]")

    return "\n".join(lines)
