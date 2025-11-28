from odoo import models, fields, api

class AdsAd(models.Model):
    _name = "ads.ad"
    _description = "Ads Ad"

    name = fields.Char()
    external_id = fields.Char(help="platform::ad_id", index=True)
    platform_ad_id = fields.Char()
    creative_id = fields.Char()
    thumbnail_url = fields.Char()
    status = fields.Char()
    adset_id = fields.Char()
    adset_name = fields.Char()
    daily_budget = fields.Char()
    lifetime_budget = fields.Char()
    budget_remaining = fields.Char()

    campaign_id = fields.Many2one('ads.campaign', string="Campaign")
    ad_account = fields.Char()
