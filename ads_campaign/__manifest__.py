{
    "name": "Ads Campaign Sync",
    "version": "1.0.0",
    "summary": "Sync Ads (Facebook initially) into Odoo - campaigns, ads, insights",
    "description": """
Sync Ads from external ad platforms (Facebook for v1).
- Campaigns, Ads, and Insights are stored in custom models.
- Sync using a wizard (ad_account_id + access_token) or system parameters.
""",
    "category": "Marketing",
    "author": "Your Name",
    "depends": [
        "base",
        "crm",        # optional - we don't modify core but many users use CRM
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/ads_views.xml",
        "views/ads_sync_wizard_view.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}