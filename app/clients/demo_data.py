"""本地演示用的虚构替身数据：仅在 APP_ENV=mock/dev/local 时装配，
生产环境一律走真实 CRM / 资格服务 / 小程序登录态，不读本文件。"""
from __future__ import annotations

import uuid

DEMO_CONTACT_ID = str(uuid.UUID(int=9003))

# CRM 返回的原始能力卡：故意夹带 contact_* 字段，用于演示与测试「联系方式一律不返回」。
DEMO_CRM_CARDS: dict[str, dict] = {
    "crm-org-001": {
        "short_name": "云枢科技",
        "industry": "工业软件",
        "ability_tags": ["MES 实施", "产线数字化", "数据采集", "工艺建模", "培训交付", "溢出标签"],
        "summary": "为离散制造企业提供产线数字化改造与工艺建模服务。",
        "contact_name": "不应出现的联系人",
        "contact_phone": "000-0000-0000",
    },
    "crm-org-002": {
        "short_name": "衡远咨询",
        "industry": "管理咨询",
        "ability_tags": ["组织诊断", "薪酬体系"],
        "summary": "面向中型企业提供组织与人才体系咨询服务。",
        "contact_email": "example@example.invalid",
    },
}

# 小程序登录态 token -> contact_id，仅用于本地演示。
DEMO_MINI_TOKENS: dict[str, str] = {
    "demo-member-token": DEMO_CONTACT_ID,
}

# 资格服务返回的预设状态；未命中的课期按 can_signup 处理。
DEMO_SIGNUP_STATES: dict[str, str] = {}


__all__ = [
    "DEMO_CONTACT_ID",
    "DEMO_CRM_CARDS",
    "DEMO_MINI_TOKENS",
    "DEMO_SIGNUP_STATES",
]
