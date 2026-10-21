"""Native Hermes skill registration; never copies into the user's skill tree."""
from pathlib import Path

BUNDLED_SKILLS = {
    "hosts": "Configure and troubleshoot local, remote, and SSH Paseo daemon hosts without changing unrelated systems.",
    "monitoring": "Monitor worker events, recover catch-up cursors, and diagnose notification capture and delivery.",
    "orchestrate": "Delegate and track asynchronous Paseo coding workers across local, remote, or SSH hosts.",
    "permissions": "Present exact Paseo permission requests and apply a user's host-scoped allow/deny decision.",
    "review": "Review worker outcomes, verify evidence, and coordinate scoped follow-ups or independent review.",
}


def register_skills(ctx):
    root = Path(__file__).resolve().parent.parent / "skills"
    for name, description in BUNDLED_SKILLS.items():
        ctx.register_skill(name, root / name / "SKILL.md", description=description)
