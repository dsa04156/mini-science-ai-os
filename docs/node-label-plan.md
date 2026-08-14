# Node label plan (not applied)

기존 Label을 덮어쓰지 않기 위해 custom prefix를 사용합니다. 조사 결과를 바탕으로 아래 Patch를 먼저 검토한 뒤 별도 승인 후 적용합니다. 현재 자동 Label Patch는 수행하지 않았습니다.

## 예정 Patch

```yaml
apiVersion: v1
kind: Node
metadata:
  name: etri-ser0001-cg0msb
  labels:
    science-ai.io/site: etri-lab
    science-ai.io/execution-class: gpu
    science-ai.io/architecture: amd64
    science-ai.io/accelerator-vendor: nvidia
    science-ai.io/accelerator-mode: hami
---
apiVersion: v1
kind: Node
metadata:
  name: etri-ser0002-cgnmsb
  labels:
    science-ai.io/site: etri-lab
    science-ai.io/execution-class: gpu
    science-ai.io/architecture: amd64
    science-ai.io/accelerator-vendor: nvidia
    science-ai.io/accelerator-mode: hami
---
apiVersion: v1
kind: Node
metadata:
  name: etri-dev0001-jetorn
  labels:
    science-ai.io/site: etri-lab
    science-ai.io/execution-class: edge
    science-ai.io/architecture: arm64
```

Raspberry Pi 노드에는 `science-ai.io/execution-class=edge`, `science-ai.io/architecture=arm64`를 추가할 수 있습니다. 이 계획은 기존 `environment`, `gpu`, `accelerator`, `edge.device/*` 값을 변경하지 않습니다. Kueue와 API MVP는 기존의 확인된 `environment=cloud`, `gpu.platform=server`, `kubernetes.io/arch=amd64` label을 사용하므로 이 Patch 없이도 동작하도록 작성합니다.

