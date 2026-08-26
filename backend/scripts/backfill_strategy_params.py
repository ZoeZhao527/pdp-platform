"""为历史策略卡补全结构化参数，已有值不覆盖。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.models import Strategy  # noqa: E402

DEFAULTS = {
    "channels": "朋友圈,社群",
    "layers": "潜客,新客,复购",
    "kpi_metrics": "转化率,GMV,复购率",
    "cadence": "每周3次",
    "cards": "",
}


def main() -> None:
    with SessionLocal() as db:
        updated = 0
        for strategy in db.query(Strategy).all():
            params = dict(strategy.params_json or {})
            changed = False
            if not params.get("activity_type"):
                params["activity_type"] = strategy.name
                changed = True
            for key, default in DEFAULTS.items():
                if key not in params or params.get(key) in (None, ""):
                    params[key] = default
                    changed = True
            if changed:
                strategy.params_json = params
                updated += 1
        db.commit()
        print(f"已补全 {updated} 条历史策略参数")


if __name__ == "__main__":
    main()
