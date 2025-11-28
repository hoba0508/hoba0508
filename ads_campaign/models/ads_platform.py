from odoo import models, fields

class AdsPlatform(models.Model):
    _name = "ads.platform"
    _description = "Ads Platform"

    name = fields.Char(required=True, help="Platform key (e.g. facebook, google)")
    display_name = fields.Char()
