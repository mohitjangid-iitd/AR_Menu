"""
db/__init__.py — Convenience re-exports

Baaki codebase ko sirf yahi import karna hai:
    from db import get_db, init_all, ...

Ya seedha module se:
    from db.core import get_orders
    from db.staff import verify_staff
"""

# Connection
from db.connection import get_db, _pool, _PgConn

# Core ops
from db.core_db import (
    init_core_tables,
    # table ops
    seed_tables, activate_table, activate_all_tables,
    close_table, close_all_tables,
    get_table_status, get_all_tables, get_table_summary,
    # order ops
    place_order, get_orders, update_order_status,
    update_ready_items, get_table_orders_detail,
    # bill ops
    generate_bill, get_bill, mark_bill_paid,
    # waiter calls
    create_waiter_call, get_active_calls, resolve_waiter_call,
    # analytics
    get_summary, get_analytics,
    get_today_sales, get_total_orders_today,
    get_top_selling_items, get_lowest_selling_items,
    get_revenue_summary,
    # export
    export_full_db_zip,
)

# Staff
from db.staff_db import (
    init_staff_tables,
    create_staff, verify_staff, get_staff_list,
    update_staff_password, toggle_staff_active, delete_staff,
)

# Admin
from db.admin_db import (
    init_admin_tables,
    create_admin, verify_admin,
    get_site_setting, set_site_setting, get_all_site_settings,
    get_overall_stats, get_top_dishes_overall, get_all_restaurants_info,
)

# Owner
from db.owner_db import (
    init_owner_tables,
    create_signup_request, get_signup_requests, get_signup_request,
    approve_signup_request, reject_signup_request,
    create_owner, verify_owner, get_owner_by_client_id,
    toggle_owner_active, update_owner_password,
)

# Customer
from db.customer_db import (
    init_customer_tables,
    get_or_create_customer, get_customer_by_id,
    update_customer_profile, get_customer_orders,
)

# Restaurant + Trash
from db.restaurant_db import (
    init_restaurant_tables,
    save_restaurant_json, get_restaurant_branches, delete_restaurant_full,
    trash_add, trash_get_all, trash_get_one,
    trash_remove, trash_remove_by_client, trash_remove_all, trash_remove_expired,
)

# Blog
from db.blog_db import (
    init_blog_tables,
    create_blog_post, update_blog_post,
    submit_for_review, publish_post, reject_post, archive_post, unarchive_post,
    delete_post,
    get_post_by_id, get_post_by_slug,
    get_posts, get_pending_review_posts, get_published_posts,
    get_posts_by_tag, count_posts_by_tag, count_posts,
    slug_exists, generate_unique_slug,
)

# Billing
from db.billing_db import init_billing_tables


def init_all():
    """
    Main lifespan mein ek baar call karo — saari tables create ho jaayengi.
    Order matters: customer pehle (orders mein FK hai), phir core, phir rest.
    """
    init_customer_tables()    # customers (FK in orders)
    init_core_tables()        # tables, orders, bills
    init_staff_tables()       # staff
    init_admin_tables()       # admins, site_settings
    init_owner_tables()       # owner_signup_requests, owners
    init_restaurant_tables()  # restaurants, trash_meta
    init_billing_tables()     # subscriptions, plans, addons, etc.
    init_blog_tables()        # blog_posts
    print("[OK] All DB tables initialized")
