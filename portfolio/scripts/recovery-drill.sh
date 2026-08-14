#!/usr/bin/env bash
set -euo pipefail

mode="${1:-plan}"
backup_dir="${BACKUP_DIR:-}"
restore_namespace="science-ai-restore-drill"

usage() {
  printf '%s\n' \
    'usage: recovery-drill.sh plan|backup|restore' \
    '  backup: BACKUP_DIR=/absolute/private/path CONFIRM_BACKUP_READ=kubeflow/mysql' \
    '  restore: BACKUP_DIR=/absolute/private/path CONFIRM_RESTORE_NAMESPACE=science-ai-restore-drill'
}

require_backup_dir() {
  [[ -n "${backup_dir}" ]] || { printf 'ERROR: BACKUP_DIR is required.\n' >&2; exit 2; }
  [[ "${backup_dir}" = /* ]] || { printf 'ERROR: BACKUP_DIR must be an absolute path.\n' >&2; exit 2; }
  case "${backup_dir}" in
    /|/home|/home/*/codex-work/platform|/home/*/codex-work/platform/*)
      printf 'ERROR: BACKUP_DIR must not be a home, workspace, or repository path.\n' >&2
      exit 2
      ;;
  esac
}

plan() {
  cat <<'EOF'
Recovery drill plan (no cluster changes):
1. Read-only preflight: verify kubeflow/mysql and science-ai-mlops/minio readiness.
2. Backup: stream a consistent all-databases mysqldump to a private directory.
3. Record: store manifest inventory and SHA-256 without exporting Kubernetes Secrets.
4. Restore: create only the fixed namespace science-ai-restore-drill with an emptyDir MySQL.
5. Verify: import the dump, list restored databases, record evidence, then delete that namespace.

Safety boundaries:
- backup and restore require separate exact confirmation variables;
- the restore never writes to the source MySQL or source PVC;
- the script refuses repository/home backup paths;
- MinIO objects are inventoried only; remote object backup remains a documented gap.
EOF
}

backup() {
  require_backup_dir
  [[ "${CONFIRM_BACKUP_READ:-}" == "kubeflow/mysql" ]] || {
    printf 'ERROR: set CONFIRM_BACKUP_READ=kubeflow/mysql.\n' >&2
    exit 2
  }
  umask 077
  mkdir -p "${backup_dir}"
  chmod 700 "${backup_dir}"

  kubectl rollout status deployment/mysql -n kubeflow --timeout=120s
  kubectl rollout status statefulset/minio -n science-ai-mlops --timeout=120s

  kubectl exec -n kubeflow deployment/mysql -c mysql -- \
    sh -c 'exec mysqldump -uroot -p"${MYSQL_ROOT_PASSWORD}" --all-databases --single-transaction --routines --events --hex-blob' \
    >"${backup_dir}/mysql-all-databases.sql"

  kubectl get deployment/mysql service/mysql pvc/mysql-pv-claim -n kubeflow \
    -o yaml >"${backup_dir}/kubeflow-inventory.yaml"
  kubectl get statefulset,service,pvc -n science-ai-mlops \
    -l 'science-ai.io/managed-by=mini-science-ai-os' -o yaml >"${backup_dir}/minio-inventory.yaml"
  kubectl exec -n science-ai-mlops statefulset/minio -c minio -- \
    sh -c 'du -sk /data 2>/dev/null || true' >"${backup_dir}/minio-size-kib.txt"

  sha256sum "${backup_dir}/mysql-all-databases.sql" >"${backup_dir}/SHA256SUMS"
  [[ -s "${backup_dir}/mysql-all-databases.sql" ]] || {
    printf 'ERROR: MySQL dump is empty.\n' >&2
    exit 1
  }
  printf 'Backup captured in private directory: %s\n' "${backup_dir}"
  printf 'MinIO data was inventoried, not copied.\n'
}

restore() {
  require_backup_dir
  [[ "${CONFIRM_RESTORE_NAMESPACE:-}" == "${restore_namespace}" ]] || {
    printf 'ERROR: set CONFIRM_RESTORE_NAMESPACE=%s.\n' "${restore_namespace}" >&2
    exit 2
  }
  dump="${backup_dir}/mysql-all-databases.sql"
  sums="${backup_dir}/SHA256SUMS"
  [[ -s "${dump}" && -s "${sums}" ]] || {
    printf 'ERROR: backup dump or checksum is missing.\n' >&2
    exit 2
  }
  (cd "${backup_dir}" && sha256sum -c SHA256SUMS)
  if kubectl get namespace "${restore_namespace}" >/dev/null 2>&1; then
    printf 'ERROR: namespace %s already exists; refusing to reuse it.\n' "${restore_namespace}" >&2
    exit 2
  fi

  created=0
  cleanup() {
    if [[ "${created}" == "1" ]]; then
      kubectl delete namespace "${restore_namespace}" --wait=true --timeout=180s >/dev/null
    fi
  }
  trap cleanup EXIT

  restore_password="$(openssl rand -hex 24)"
  kubectl create namespace "${restore_namespace}" >/dev/null
  created=1
  kubectl label namespace "${restore_namespace}" \
    pod-security.kubernetes.io/enforce=baseline \
    science-ai.io/managed-by=mini-science-ai-os >/dev/null
  kubectl create secret generic mysql-restore-auth -n "${restore_namespace}" \
    --from-literal=password="${restore_password}" >/dev/null
  unset restore_password

  kubectl apply -n "${restore_namespace}" -f - >/dev/null <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mysql-restore
  labels:
    app.kubernetes.io/name: mysql-restore
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: mysql-restore
  template:
    metadata:
      labels:
        app.kubernetes.io/name: mysql-restore
    spec:
      automountServiceAccountToken: false
      securityContext:
        runAsNonRoot: true
        runAsUser: 999
        runAsGroup: 999
        fsGroup: 999
        fsGroupChangePolicy: OnRootMismatch
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: mysql
          image: docker.io/library/mysql@sha256:b3b90af2a6552ae30c266fdb7d5dd55f3afb72404bb78d37fe8a23eb857fd3fb
          env:
            - name: MYSQL_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: mysql-restore-auth
                  key: password
          resources:
            requests:
              cpu: 100m
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 2Gi
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: data
              mountPath: /var/lib/mysql
      volumes:
        - name: data
          emptyDir: {}
EOF

  kubectl rollout status deployment/mysql-restore -n "${restore_namespace}" --timeout=180s
  kubectl exec -i -n "${restore_namespace}" deployment/mysql-restore -c mysql -- \
    sh -c 'exec mysql -uroot -p"${MYSQL_ROOT_PASSWORD}"' <"${dump}"
  kubectl exec -n "${restore_namespace}" deployment/mysql-restore -c mysql -- \
    sh -c 'exec mysql -N -uroot -p"${MYSQL_ROOT_PASSWORD}" -e "SHOW DATABASES"' \
    | tee "${backup_dir}/restore-databases.txt"
  grep -Fxq 'mlpipeline' "${backup_dir}/restore-databases.txt"
  printf 'Restore verification succeeded in isolated namespace %s; cleanup follows.\n' "${restore_namespace}"
}

case "${mode}" in
  plan) plan ;;
  backup) backup ;;
  restore) restore ;;
  -h|--help) usage ;;
  *) usage >&2; exit 2 ;;
esac
