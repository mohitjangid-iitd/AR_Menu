"""
feature_registry.py — ZenTable Feature Registry

SIRF DO KAAM KARTA HAI:
1. App mein kaun se features exist karte hain — keys
2. Naye features ka default label — pehli baar DB mein seed hone ke liye

Plan mapping (kaunse plan mein kya milega) DB mein hai — admin panel se editable.
Yahan SIRF naya feature add karo, plan assignment admin karega ya DEFAULT_PLAN_MAP se.
"""

# key → default label
FEATURES = {
    # ── Core (sab plans mein) ──
    "website":               "Personal Website",
    "qr_ordering":           "QR Ordering + Digital Menu",
    "digital_menu":          "Digital Menu",
    "staff_panel":           "Staff Panel (Waiter/Kitchen/Counter)",
    "basic_pos":             "Basic POS",
    "ai_menu_import":        "Photo to Menu (AI)",
    "blog":                  "Personal Blog Page",

    # ── Pro + Elite ──
    "owner_analytics":       "Owner Analytics Dashboard",
    "ai_chatbot":            "AI Chat Support",
    "multi_branch":          "Multi-branch / Outlets",

    # ── Elite only ──
    "centralized_reporting": "Centralized Reporting",
    "custom_integrations":   "Custom Integrations",
    "dedicated_support":     "Dedicated Account Manager",

    # ── Addons ──
    "ar_menu":               "AR Menu (3D Dish Preview)",
    "kitchen_tab":           "Kitchen Display Tab",
    "attendance":            "Staff Attendance & Shift Mgmt",

    # ── Naye features — yahan uncomment karo jab ready ho ──
    # "inventory":           "Inventory Management",
}

# Ye keys addon hain — plan mein include nahi hote, alag khareedne padte hain
ADDON_FEATURES = {"ar_menu", "kitchen_tab", "attendance"}

# Naye feature ka default plan assignment — sync_plan_features() use karta hai
# Sirf tab matter karta hai jab feature pehli baar DB mein add ho raha ho
# Baad mein admin panel se toggle kar sakte hain
DEFAULT_PLAN_MAP = {
    #  key                    basic   pro    elite
    "website":               (True,  True,  True),
    "qr_ordering":           (True,  True,  True),
    "digital_menu":          (True,  True,  True),
    "staff_panel":           (True,  True,  True),
    "basic_pos":             (True,  True,  True),
    "ai_menu_import":        (True,  True,  True),
    "blog":                  (True,  True,  True),
    "owner_analytics":       (False, True,  True),
    "ai_chatbot":            (False, True,  True),
    "multi_branch":          (False, True,  True),
    "centralized_reporting": (False, False, True),
    "custom_integrations":   (False, False, True),
    "dedicated_support":     (False, False, True),
    "ar_menu":               (False, False, False),  # addon
    "kitchen_tab":           (False, False, False),  # addon
    "attendance":            (False, False, False),  # addon
    # "inventory":           (False, True,  True),   # naye ke saath yahan bhi add karo
}


def all_feature_keys() -> list[str]:
    return list(FEATURES.keys())


def feature_label(key: str) -> str:
    return FEATURES.get(key, key)


def is_addon_feature(key: str) -> bool:
    return key in ADDON_FEATURES
