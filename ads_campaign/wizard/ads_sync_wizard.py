import json
import logging
import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v24.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

class AdsSyncWizard(models.TransientModel):
    _name = "ads.sync.wizard"
    _description = "Wizard to sync ads from a platform"

    platform = fields.Selection([('facebook', 'Facebook')], default='facebook', required=True)
    ad_account_id = fields.Char(string="Ad Account ID", help="If empty, will use system parameter meta.ad_account_id")
    access_token = fields.Char(string="Access Token", help="If empty, will use system parameter meta.access_token")

    def _get_system_param(self, key):
        return self.env['ir.config_parameter'].sudo().get_param(key, default=False)

    def action_sync(self):
        self.ensure_one()
        platform = self.platform
        ad_account = self.ad_account_id or self._get_system_param('meta.ad_account_id')
        token = self.access_token or self._get_system_param('meta.access_token')

        if not ad_account or not token:
            raise UserError(_("Ad account ID and access token are required either in the wizard or in system parameters meta.ad_account_id and meta.access_token."))

        # Build request
        endpoint = f"{GRAPH_BASE}/act_{ad_account}/ads"
        fields = "id,name,status,adset{id,name,daily_budget,lifetime_budget,budget_remaining},campaign_name,created_time,updated_time,creative{effective_object_story_id,object_story_spec{link_data{link,message,name,caption,description}},image_url,thumbnail_url,video_id},insights{impressions,reach,clicks,ctr,cpc,cpm,spend,objective,actions,inline_link_clicks,inline_post_engagement,unique_clicks,unique_ctr}&limit=100"
        params = {
            'fields': fields,
            'access_token': token,
        }

        try:
            resp = requests.get(endpoint, params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            _logger.exception("Error requesting Facebook Graph API: %s", e)
            raise UserError(_("Failed to contact Facebook Graph API: %s") % e)

        data = resp.json()
        if 'error' in data:
            _logger.error("FB API error: %s", data['error'])
            raise UserError(_("Facebook API returned an error: %s") % json.dumps(data['error']))

        created = 0
        updated = 0

        ads_model = self.env['ads.ad'].sudo()
        campaign_model = self.env['ads.campaign'].sudo()
        insight_model = self.env['ads.insight'].sudo()

        for item in data.get('data', []):
            ad_id = item.get('id')
            ad_name = item.get('name')
            status = item.get('status')
            campaign_name = item.get('campaign_name')
            adset = item.get('adset') or {}
            creative = item.get('creative') or {}
            insights = item.get('insights') or {}

            # Determine campaign id: Facebook returns campaign id in other endpoints; here we use campaign_name + adset/ad_id to generate code.
            # Prefer campaign id if available in creative or elsewhere; else we use ad_id as fallback for deterministic code
            # For this example, we will set platform_campaign_id = campaign_name (string) if id isn't available.
            platform_campaign_id = campaign_name or "unknown_campaign"

            # Create or get campaign
            campaign = campaign_model.get_or_create_campaign(
                platform_key=platform,
                ad_account=ad_account,
                platform_campaign_id=platform_campaign_id,
                campaign_name=campaign_name,
            )

            external_ad_id = f"{platform}::{ad_id}"
            ad_vals = {
                'name': ad_name,
                'external_id': external_ad_id,
                'platform_ad_id': ad_id,
                'creative_id': creative.get('id'),
                'thumbnail_url': creative.get('thumbnail_url') or creative.get('image_url'),
                'status': status,
                'adset_id': adset.get('id'),
                'adset_name': adset.get('name'),
                'daily_budget': adset.get('daily_budget'),
                'lifetime_budget': adset.get('lifetime_budget'),
                'budget_remaining': adset.get('budget_remaining'),
                'campaign_id': campaign.id,
                'ad_account': ad_account,
            }

            existing = ads_model.search([('external_id', '=', external_ad_id)], limit=1)
            if existing:
                existing.sudo().write(ad_vals)
                updated += 1
                ad_rec = existing
            else:
                ad_rec = ads_model.create(ad_vals)
                created += 1

            # Insights may be nested: item['insights']['data'] is a list
            insights_data = insights.get('data') if isinstance(insights, dict) else None
            if insights_data:
                for ins in insights_data:
                    # Save or update insight by ad + date range
                    date_start = ins.get('date_start')
                    date_stop = ins.get('date_stop')
                    # find existing same date_start/stop
                    existing_ins = insight_model.search([('ad_id', '=', ad_rec.id), ('date_start', '=', date_start), ('date_stop', '=', date_stop)], limit=1)
                    ins_vals = {
                        'ad_id': ad_rec.id,
                        'date_start': date_start,
                        'date_stop': date_stop,
                        'impressions': ins.get('impressions'),
                        'reach': ins.get('reach'),
                        'clicks': ins.get('clicks'),
                        'ctr': ins.get('ctr'),
                        'cpc': ins.get('cpc'),
                        'cpm': ins.get('cpm'),
                        'spend': ins.get('spend'),
                        'objective': ins.get('objective'),
                        'actions': json.dumps(ins.get('actions')) if ins.get('actions') else None,
                    }
                    if existing_ins:
                        existing_ins.sudo().write(ins_vals)
                    else:
                        insight_model.create(ins_vals)

        msg = _("Sync finished. Created: %d, Updated: %d") % (created, updated)
        # show message via wizard exit
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Ads Sync',
                'message': msg,
                'sticky': False,
            }
        }
