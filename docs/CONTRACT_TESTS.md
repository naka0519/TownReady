# Contract Tests（API I/O 検証）

Pydantic モデルの JSON Schema と、サンプル I/O の整合性を検証する最小の手順です。

## 1) JSON Schema の生成

```bash
# 生成物は schemas/json/*.schema.json に出力
python -m schemas.generate_json_schema
```

## 2) サンプル I/O のバリデーション

- GenerateBaseRequest などの JSON を検証するための簡易スクリプトを用意します。

```bash
python - <<'PY'
from pathlib import Path
import json
from pydantic import ValidationError
try:
    from GCP_AI_Agent_hackathon.schemas import GenerateBaseRequest
except Exception:
    import sys
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from schemas import GenerateBaseRequest  # type: ignore

# README の例
sample = {
  "location": {"address": "横浜市瀬谷区＊＊＊", "lat": 35.47, "lng": 139.49},
  "participants": {"total": 120, "children": 25, "elderly": 18, "wheelchair": 3, "languages": ["ja", "en"]},
  "hazard": {"types": ["earthquake", "fire"], "drill_date": "2025-10-12", "indoor": True, "nighttime": False},
  "constraints": {"max_duration_min": 45, "limited_outdoor": True},
  "kb_refs": ["kb://yokohama_guideline", "kb://shelter_rules"]
}

try:
    obj = GenerateBaseRequest.model_validate(sample)
    print("OK: GenerateBaseRequest is valid")
except ValidationError as e:
    print("ERROR: validation failed\n", e)
PY
```

## 3) CI への組込（例）

- Cloud Build / GitHub Actions などで `python -m schemas.generate_json_schema` と上記バリデーションを走らせるだけでも効果があります。
- 追加で、`curl` による API 応答のスキーマ整合（`jq` で key の有無チェック等）も推奨です。

---

## 付録: 追加サンプル

- `tmp/plan.json` / `tmp/content.json` を使った API 起動 → job_id → `GET /api/jobs/{id}` の項目チェックは `docs/E2E_SMOKE.md` を参照。
