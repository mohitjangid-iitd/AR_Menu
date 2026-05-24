# check_feature_gates.py
# Run: python check_feature_gates.py

from billing_db import get_all_subscriptions, has_feature
from feature_registry import FEATURES


def audit():
    subs = get_all_subscriptions()
    if not subs:
        print("Koi subscription nahi mili.")
        return

    keys = list(FEATURES.keys())
    header = f"{'Client':<20} {'Status':<10} {'Plan':<8}"
    for k in keys:
        header += f" {k[:10]:<11}"
    print(header)
    print("─" * len(header))

    for sub in subs:
        cid  = sub["client_id"]
        row  = f"{cid:<20} {sub['status']:<10} {sub.get('plan_key','—'):<8}"
        for k in keys:
            row += f" {'✅'if has_feature(cid,k) else '🔒':<11}"
        print(row)


if __name__ == "__main__":
    audit()
