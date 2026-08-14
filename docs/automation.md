# Automation and scheduled work

이 MVP에는 CronJob이나 자율 Rescheduler가 없다. `make inventory`, `validate`, `bootstrap`, `demo`, `test`, `destroy-demo`는 운영자의 명시적 동작이며 Kueue만 Job 입장 상태를 자동 조정한다.

운영 자동화에는 Unit/Manifest/Policy/Image Scan, Signed Digest, External Secret, KFP MySQL·MinIO Backup, Audit Export, Alert Paging을 추가해야 한다. 기존 HAMi, Prometheus/Grafana, Argo CD, KubeEdge 또는 보안 정책을 Agent가 자율 변경해서는 안 된다.
