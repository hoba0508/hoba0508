# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AdsSyncWizard(models.TransientModel):
    _name = "ads.sync.wizard"
    _description = "Ads Sync Wizard"

    platform = fields.Selection([
        ("facebook", "Facebook"),
        ("google", "Google"),
        ("other", "Other"),
    ], string="Platform", required=True, default="facebook")
    ad_account_id = fields.Char(string="Ad Account ID", help="Optional. If empty, system parameter 'meta.ad_account_id' will be used.")
    access_token = fields.Char(string="Access Token", help="Optional. If empty, system parameter 'meta.access_token' will be used.")

    def action_sync(self):
        """Call appropriate sync routine based on platform. Returns a simple client action."""
        self.ensure_one()
        if self.platform == "facebook":
            # call model method to sync
            ads_campaign = self.env["ads.campaign"]
            try:
                res = ads_campaign.sync_from_facebook(self.ad_account_id, self.access_token)
            except Exception as e:
                raise UserError(_("Sync failed: %s") % (e,))
            # show simple message
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Ads Sync"),
                    "message": _("Sync finished: created %(c)s, updated %(u)s") % {"c": res.get("created", 0), "u": res.get("updated", 0)},
                    "sticky": False,
                },
            }
        else:
            raise UserError(_("Platform %s not yet implemented.") % (self.platform,))
