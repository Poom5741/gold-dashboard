"""APScheduler setup — Asia/Bangkok cron per SPEC §7 + D1, with recovery (D8).

Sun 18:00 weekly brief (runs refresh first) · Mon–Fri 07:00 macro+price ·
Mon–Fri 14:00 options+bias · plus Saturday 07:00 refresh so the Sunday brief
has Friday's close and the latest COT release.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

BANGKOK = ZoneInfo("Asia/Bangkok")


def build_scheduler(store, settings, cfg, refresh_fn, bias_fn, report_fn):
    sched = BackgroundScheduler(timezone=str(BANGKOK))
    jobs = cfg["scheduler"]
    w = jobs["weekly_brief"]
    m = jobs["macro_price"]
    o = jobs["options_bias"]

    common = dict(misfire_grace_time=3600, coalesce=True)  # D8

    def weekly_brief():
        refresh_fn()
        as_of = datetime.now(timezone.utc).isoformat()
        bias = bias_fn(as_of, kind="weekly_brief")
        report_fn(bias)

    def macro_price():
        refresh_fn()
        bias_fn(datetime.now(timezone.utc).isoformat(), kind="daily_bias")

    def options_bias():
        bias_fn(datetime.now(timezone.utc).isoformat(), kind="daily_bias")

    sched.add_job(weekly_brief, CronTrigger(day_of_week=w["day_of_week"], hour=w["hour"],
                                            minute=w["minute"], timezone=str(BANGKOK)),
                  id="weekly_brief", **common)
    sched.add_job(macro_price, CronTrigger(day_of_week=m["day_of_week"], hour=m["hour"],
                                           minute=m["minute"], timezone=str(BANGKOK)),
                  id="macro_price", **common)
    sched.add_job(options_bias, CronTrigger(day_of_week=o["day_of_week"], hour=o["hour"],
                                            minute=o["minute"], timezone=str(BANGKOK)),
                  id="options_bias", **common)
    return sched


def startup_catchup(store, refresh_fn, bias_fn, report_fn, cfg) -> list[str]:
    """Regenerate missed runs on boot (D8): brief older than N days, bias older than M."""
    actions: list[str] = []
    from .store import utcnow

    c = cfg["scheduler"]["catchup"]
    brief_age = store.last_snapshot_age_days("weekly_brief", utcnow())
    if brief_age is None or brief_age > c["weekly_brief_max_age_days"]:
        refresh_fn()
        as_of = datetime.now(timezone.utc).isoformat()
        bias = bias_fn(as_of, kind="weekly_brief")
        report_fn(bias)
        actions.append("regenerated weekly brief (catch-up)")
    bias_age = store.last_snapshot_age_days("daily_bias", utcnow())
    if bias_age is None or bias_age > c["daily_bias_max_age_days"]:
        as_of = datetime.now(timezone.utc).isoformat()
        bias_fn(as_of, kind="daily_bias")
        actions.append("regenerated daily bias (catch-up)")
    return actions


def job_specs(cfg) -> dict[str, dict]:
    """Expose configured job specs for /api/schedule (test control REQ-7)."""
    specs = {}
    for name, j in cfg["scheduler"].items():
        if name == "catchup":
            continue
        specs[name] = {
            "day_of_week": j["day_of_week"], "hour": j["hour"], "minute": j["minute"],
            "timezone": "Asia/Bangkok",
        }
    return specs
