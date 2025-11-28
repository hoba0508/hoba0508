# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class AdsCampaign(models.Model):
    _name = "ads.campaign"
    _description = "Ads Campaign"
    _order = "id desc"

    name = fields.Char(string="Campaign Name")
    code = fields.Char(string="Campaign Code", required=True)  # unique across platforms
    platform_id = fields.Many2one('ads.platform', string="Platform", required=True)
    platform_campaign_id = fields.Char(string="Platform Campaign ID")
    ad_account = fields.Char(string="Ad Account")
    external_id = fields.Char(string="External ID", help="platform::id")
    status = fields.Char()
    start_date = fields.Datetime()
    end_date = fields.Datetime()
    description = fields.Text()

    _sql_constraints = [
        ('campaign_code_uniq', 'UNIQUE(code)', 'Campaign code must be unique across all platforms.'),
    ]

    @api.model
    def get_or_create_campaign(self, platform_key, ad_account, platform_campaign_id, campaign_name=None, vals=None):
        """Return existing campaign or create one. Generates deterministic code."""
        vals = vals or {}
        platform = self.env['ads.platform'].sudo().search([('name', '=', platform_key)], limit=1)
        if not platform:
            platform = self.env['ads.platform'].sudo().create({'name': platform_key, 'display_name': platform_key.capitalize()})

        external_id = f"{platform_key}::{platform_campaign_id}" if platform_campaign_id else False
        # Code format: PLATFORM_<AD_ACCOUNT>_<CAMPAIGN_ID>
        code = f"{platform_key.upper()}_{ad_account}_{platform_campaign_id}" if platform_campaign_id else f"{platform_key.upper()}_{ad_account}_{abs(hash(campaign_name or 'unknown'))}"

        campaign = self.sudo().search([('code', '=', code)], limit=1)
        if campaign:
            return campaign
        vals_full = {
            'name': campaign_name or platform_campaign_id or 'Unknown Campaign',
            'code': code,
            'platform_id': platform.id,
            'platform_campaign_id': platform_campaign_id,
            'ad_account': ad_account,
            'external_id': external_id,
        }
        vals_full.update(vals)
        return self.sudo().create(vals_full)
