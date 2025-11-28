from odoo import models, fields

class AdsInsight(models.Model):
    _name = "ads.insight"
    _description = "Ads Insight (metrics per ad)"

    ad_id = fields.Many2one('ads.ad', string="Ad", ondelete='cascade')
    date_start = fields.Date()
    date_stop = fields.Date()
    impressions = fields.Char()
    reach = fields.Char()
    clicks = fields.Char()
    ctr = fields.Char()
    cpc = fields.Char()
    cpm = fields.Char()
    spend = fields.Char()
    objective = fields.Char()
    actions = fields.Text(string="Actions JSON")
