"""导出本单响应 schema 到 openapi/academy_course_detail_1918.json。

用法：python scripts/export_openapi.py
输出：openapi/academy_course_detail_1918.json（全量 openapi 3.1，含本单 5 个组件）"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main import create_app  # noqa: E402


def main() -> int:
    app = create_app(init_db=False)
    schema = app.openapi()
    for name in (
        "AcademyCourseDetail",
        "InstructorItem",
        "CompanyCard",
        "SessionItem",
        "ReviewItem",
        "ReviewSummary",
    ):
        if name not in schema["components"]["schemas"]:
            print(f"missing component: {name}", file=sys.stderr)
            return 1
    out = ROOT / "openapi" / "academy_course_detail_1918.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size} bytes)")
    print(f"components={len(schema['components']['schemas'])} paths={len(schema['paths'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
