# Phase 1 — K8s Security Audit Pipeline (Alloy + Loki)

Rides on Project 1's existing EKS cluster and `monitoring` namespace
(kube-prometheus-stack). No second Grafana, no parallel cluster.

## What's here

| File | Purpose |
| --- | --- |
| `audit-policy.yaml` | Intent-level audit policy: RBAC writes + `pods/exec`/`attach` at full detail, everything else dropped or thin. See in-file comment on the EKS control-plane caveat. |
| `alloy-config.alloy` | Alloy pipeline: pull EKS audit events from CloudWatch, filter to the two categories, push to Loki. |
| `gitops/loki.yaml` | Argo CD Application — Loki, single-binary, filesystem-backed, into `monitoring`. |
| `gitops/alloy.yaml` | Argo CD Application — Alloy, one replica, IRSA-scoped to read the audit log group only. |
| `alerts/security-audit-rules.yaml` | Loki ruler alerts: `RBACRoleOrBindingChanged`, `PodExecOrAttach`. Fire to the existing Alertmanager. |
| `dashboards/k8s-security-audit-dashboard.json` | Two log panels + two rate panels, import into the existing Grafana. |

## EKS-specific setup

EKS doesn't let you pass `--audit-policy-file` to a self-managed
`kube-apiserver` — the control plane is managed. Audit logging is a
cluster-level API/console toggle instead:

```bash
aws eks update-cluster-config \
  --name <your-cluster-name> \
  --logging '{"clusterLogging":[{"types":["audit"],"enabled":true}]}'
```

This ships **all** audit events to a CloudWatch Logs group
(`/aws/eks/<cluster-name>/cluster`, stream prefix `kube-apiserver-audit-`).
`audit-policy.yaml` in this folder describes the filtering you want; on EKS
that filtering happens client-side, in Alloy, not server-side via the policy
file. That's why `alloy-config.alloy` has an explicit `loki.process` stage
that drops everything except RBAC writes and pod exec/attach — treat the
policy YAML as the spec Alloy's filter stage implements, not something you
hand to the apiserver directly.

IAM: the Alloy service account (IRSA) needs read-only
`logs:FilterLogEvents` / `logs:GetLogEvents` scoped to that one log group —
nothing else. Least privilege, matching how Project 1's IRSA roles are
scoped elsewhere in this portfolio.

## Verification checkpoint

1. `kubectl create rolebinding test-rb --clusterrole=view --user=test-user -n httpbin`
   → confirm it shows up in the RBAC panel within ~1 minute.
2. `kubectl exec -it -n httpbin <any-httpbin-pod> -- /bin/sh`
   → confirm it shows up in the exec panel within seconds.
3. Screenshot both. That screenshot is the Phase 1 checkpoint the plan asks
   for — this repo ships the code to produce it, not the screenshot itself,
   since it needs your real, running cluster.

## Status

Code-complete, not yet run against a live cluster — same verification
posture as Project 1's Phase 2–4 additions. Expect small first-contact
fixes (a Helm values field renamed between chart versions, the CloudWatch
IAM policy needing one more action) — that debugging is itself covered as
an exercise in the study guide.
