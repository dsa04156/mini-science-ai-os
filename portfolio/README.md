# NAIS 기술직-1 증거 패키지

이 디렉터리는 `mini-science-ai-os`를 국가과학AI연구센터(NAIS) 기술직-1
`통합플랫폼연구/플랫폼개발` 직무와 대조해 검토할 수 있도록 만든 면접용
증거 패키지다. 제품의 실제 구현과 아직 구현되지 않은 부분을 분리한다.

## 30초 제품 화면

![NAIS Science Workspace 실제 장비 운영 대시보드](screenshots/operations-dashboard-desktop.png)

이 화면은 2026-08-18 실제 랩 장비에서 수집한 상태다. 5개 노드의 Ready·CPU·Memory·Architecture, 2개 물리 GPU의 DCGM 사용량·온도·전력, HAMi 논리 할당, Kueue 입장 상태와 8개 핵심 플랫폼 구성요소를 한 화면에서 교차 확인한다. 상단의 Live Evidence Spine은 동일한 실행의 Kubeflow 성공, MLflow Run·candidate 모델, Grafana 관측 상태를 실제 링크로 연결한다. 실시간 값은 장비 상태에 따라 달라진다.

모바일 검수 화면은 [operations-dashboard-mobile.png](screenshots/operations-dashboard-mobile.png), API·배포 소스는 [workspace-topology](../workspace-topology)에 있다.

## 빠른 검토 순서

1. 위 운영 대시보드에서 실제 장비와 실행 증거 확인
2. [직무요건-증거 매핑](nais-technical-1-matrix.md)
3. [10분 발표안](presentation.md)
4. [라이브 데모 동선](live-demo.md)
5. [MLflow + Grafana 기능 실증](mlflow-grafana-demo/README.md)
6. [복구 훈련](scripts/recovery-drill.sh)
7. [가용성 훈련](scripts/resilience-drill.sh)
8. [보안 검토 결과](security-review.md)
9. [보안 정적 검사](scripts/security-check.sh)

## 상태 표기

- `VERIFIED`: 저장소의 자동 테스트 또는 보존된 라이브 증거가 있다.
- `IMPLEMENTED`: 코드나 절차가 있으나 실제 운영 환경 검증이 남았다.
- `POC`: 제품 경로에 연결되지 않은 독립 실증이다.
- `GAP`: 아직 증명하지 못한 경험 또는 운영 통제다.

다음 명령은 로컬에서 제품을 변경하지 않고 포트폴리오 패키지를 검증한다.

```bash
make portfolio-check
```

클러스터 훈련은 기본적으로 계획만 출력한다. 실제 실행은 각 문서에 적힌
명시적 확인 변수를 제공해야 하며, 운영 데이터가 아닌 격리된 복구 대상을
사용한다.

기존 `docs/`와 `documentation/`은 이 작업 환경에서 root 소유로 잠겨 있어
직무 전용 상태 갱신은 이 디렉터리에 보충했다. 제품 자체의 기존 증거 파일은
수정하지 않았으며, 현재 PoC와 훈련 상태는 직무요건 매핑표의 상태 열을 기준으로
판단한다.
