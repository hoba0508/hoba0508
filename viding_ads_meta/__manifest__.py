{
    "name": "Ads Management (Meta) Integration",
    "version": "1.0",
    "summary": "Sync Meta (Facebook) Ads into Odoo, extend Social Marketing and support lead attribution",
    "author": "You",
    "license": "LGPL-3",
    "depends": ["base", "crm", "social"],
    "data": [
        "views/social_campaign_inherit_views.xml",
        "views/ads_ad_views.xml",
        "data/cron_jobs.xml",
    ],
    "installable": True,
    "application": False,
}