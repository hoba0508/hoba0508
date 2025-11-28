# -*- coding: utf-8 -*-
{
    "name": "Ads Sync",
    "version": "1.0.0",
    "summary": "Sync Ads from ad platforms (Facebook first) into a custom ads/campaign model",
    "description": "Custom module to sync ad data from platforms (Facebook initially) into a custom model. Uses system parameters if credentials are blank in the form.",
    "author": "You",
    "website": "",
    "license": "LGPL-3",
    "category": "Marketing",
    "depends": ["base", "crm", "social"],
    "data": [
        "security/ir.model.access.csv",
        "views/ads_campaign_views.xml",
        "views/ads_sync_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
