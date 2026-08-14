# Apple design explainer deployment — 2026-08-11

## 변경 파일

- `apps/docs-site/site/index.html`
- `output/playwright/apple-design-desktop.png`
- `output/playwright/apple-design-mobile.png`

## 적용한 apple-design 원칙

- Platform system font, 크기별 tracking/leading, 큰 제목과 넓은 여백.
- Sticky translucent material과 `prefers-reduced-transparency` 대체 표면.
- Pointer-down 즉시 scale feedback과 짧은 release transition.
- 실행 단계 선택 시 현재 상태에서 시작하는 Web Animation.
- Scroll 진행 피드백, 단계별 공간 일관성, 구체적인 Wayfinding.
- `prefers-reduced-motion`, `prefers-contrast`, focus-visible 대응.

## 실행 명령

```text
rtk kubectl apply --server-side -k apps/docs-site
rtk kubectl rollout status deployment/mini-science-ai-os-ko-site -n science-ai-system --timeout=5m
rtk kubectl port-forward --address=0.0.0.0 -n science-ai-system svc/mini-science-ai-os-ko-site 8088:80
rtk bash .../playwright_cli.sh open http://127.0.0.1:8088
rtk bash .../playwright_cli.sh resize 1440 1024
rtk bash .../playwright_cli.sh resize 390 844
```

## 실제 결과

```text
Deployment: 1/1 Available
Pod: 1/1 Running, restarts=0
Listener: 0.0.0.0:8088
HTTP: 200
Page title: NAIS Mini Science AI OS
Desktop viewport: 1440x1024
Mobile viewport: innerWidth=390, scrollWidth=390
Execution-step interaction: PASS
Command-copy interaction: PASS
Browser console: 0 errors, 0 warnings
```

## 접근 주소

`http://192.168.0.56:8088`

Port Forward는 인증/TLS 없이 모든 인터페이스에 바인딩되어 있으므로 신뢰된 내부망 데모 용도로만 사용한다.
