import logging
import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

API_VERSION = "v24.0"
GRAPH_BASE = f"https://graph.facebook.com/{API_VERSION}"

class AdsAd(models.Model):
    _name = "ads.ad"
    _description = "Facebook Ad (synced)"

    name = fields.Char(string="Ad Name")
    fb_ad_id = fields.Char(string="Facebook Ad ID", required=True, index=True)
    status = fields.Char(string="Status")
    fb_campaign_name = fields.Char(string="FB Campaign Name")
    fb_adset_name = fields.Char(string="FB Adset Name")
    create_date_fb = fields.Datetime(string="Created on Facebook")
    update_date_fb = fields.Datetime(string="Updated on Facebook")
    thumbnail_url = fields.Char(string="Thumbnail URL")
    creative_id = fields.Char(string="Creative ID")
    objective = fields.Char(string="Objective")

    # Metrics - latest snapshot (can be aggregated or historical in ads.insight)
    impressions = fields.Integer()
    reach = fields.Integer()
    clicks = fields.Integer()
    unique_clicks = fields.Integer()
    ctr = fields.Float()
    unique_ctr = fields.Float()
    cpc = fields.Float()
    cpm = fields.Float()
    spend = fields.Float()

    # link to Odoo Campaign / social.campaign
    social_campaign_id = fields.Many2one('social.campaign', string="Odoo Social Campaign")
    # raw JSON actions for more event detail
    actions_json = fields.Text(string="Actions (raw JSON)")

    last_synced = fields.Datetime(string="Last Synced")

    _sql_constraints = [
        ('fb_ad_id_uniq', 'unique(fb_ad_id)', 'Facebook Ad ID must be unique.')
    ]

    @api.model
    def _get_fields_param(self):
        # Fields we will ask from Graph API (creative + insights)
        creative_fields = "effective_object_story_id,object_story_spec{link_data,message,caption,description},title,image_url,thumbnail_url,video_id"
        insights_fields = "impressions,reach,clicks,ctr,cpc,cpm,spend,objective,actions,inline_link_clicks,inline_post_engagement,unique_clicks,unique_ctr,date_start,date_stop"
        fields = (
            "id,name,status,adset_name,campaign_name,created_time,updated_time,"
            f"creative{{{creative_fields}}},insights{{{insights_fields}}}"
        )
        return fields

    def action_sync_meta_ads(self):
        """Manual sync for current record(s) using the parent social campaign's credentials."""
        for rec in self:
            # If this ad record was created without account info, attempt to read social_campaign
            social_campaign = rec.social_campaign_id
            if not social_campaign:
                raise UserError(_("Please set the related Social Campaign with Meta account info."))
            social_account = social_campaign.account_id or None
            # Try getting from campaign first
            ad_account = social_campaign.meta_ad_account_id or social_campaign.meta_account_id
            token = social_campaign.meta_access_token

            # Fallback to system parameters if not set in campaign
            if not ad_account or not token:
                config = self.env['ir.config_parameter'].sudo()
                ad_account = ad_account or config.get_param('meta.ad_account_id')
                token = token or config.get_param('meta.access_token')

            if not ad_account or not token:
                raise UserError(_("No Meta credentials found. Please configure in Social Campaign or System Parameters."))

            # fetch specific ad by id
            self.env['ads.ad'].browse(rec.id).with_context({'token': token})._fetch_and_update_ads(ad_account, [rec.fb_ad_id])

    @api.model
    def _fetch_and_update_ads(self, ad_account_id, fb_ad_id_list=None, access_token=None):
        """
        Core function to fetch ads from Graph API:
         - ad_account_id: string (without 'act_' prefix or with)
         - fb_ad_id_list: optional list of specific ad ids to fetch
         - access_token: if not provided, expects context['token'] or raises
        """
        token = access_token or self.env.context.get('token')
        if not token:
            raise UserError(_("Access token is required for fetching Meta Ads."))

        # normalize ad_account
        if str(ad_account_id).startswith("act_"):
            act = str(ad_account_id)
        else:
            act = f"act_{ad_account_id}"

        fields = self._get_fields_param()
        page_url = f"{GRAPH_BASE}/{act}/ads?fields={fields}&limit=100&access_token={token}"

        # If specific ad list is provided, we can fetch by ids (graph supports /?ids=id1,id2&fields=...)
        if fb_ad_id_list:
            ids = ",".join(fb_ad_id_list)
            page_url = f"{GRAPH_BASE}/?ids={ids}&fields={fields}&access_token={token}"

        # Loop pages
        while page_url:
            _logger.info("Fetching Ads page: %s", page_url)
            try:
                resp = requests.get(page_url, timeout=30)
            except Exception as e:
                _logger.exception("Request failed: %s", e)
                raise UserError(_("Failed to contact Meta Graph API: %s") % e)

            if resp.status_code != 200:
                _logger.error("Meta API error: %s", resp.text)
                raise UserError(_("Meta API error: %s") % resp.text)

            j = resp.json()

            # If fetching by ids the format is { "<adid>": {...}, ... } -- handle both shapes
            ads_list = []
            if isinstance(j, dict) and 'data' in j:
                ads_list = j.get('data', [])
            else:
                # dict shape when using ids param: keys are ids
                for k, v in j.items():
                    if isinstance(v, dict) and 'id' in v:
                        ads_list.append(v)

            for ad in ads_list:
                try:
                    insights_obj = {}
                    if ad.get('insights'):
                        # Graph returns insights.data array
                        insights = ad['insights'].get('data', [])
                        insights_obj = insights[0] if insights else {}
                    self._create_or_update_ad_from_graph(ad, insights_obj)
                except Exception:
                    _logger.exception("Failed to process ad: %s", ad.get('id'))

            # paging
            paging = j.get('paging', {})
            page_url = paging.get('next')

    def _create_or_update_ad_from_graph(self, ad_json, insights_json):
        fb_id = ad_json.get('id')
        if not fb_id:
            return

        vals = {
            'name': ad_json.get('name'),
            'status': ad_json.get('status'),
            'fb_ad_id': fb_id,
            'fb_campaign_name': ad_json.get('campaign_name'),
            'fb_adset_name': ad_json.get('adset_name'),
            'create_date_fb': ad_json.get('created_time'),
            'update_date_fb': ad_json.get('updated_time'),
            'creative_id': (ad_json.get('creative') or {}).get('id'),
            'thumbnail_url': (ad_json.get('creative') or {}).get('thumbnail_url'),
            'objective': (insights_json or {}).get('objective'),
            'actions_json': str((insights_json or {}).get('actions', [])),
            'last_synced': fields.Datetime.now(),
        }

        # numeric metrics (coerce safely)
        def n(v):
            try:
                return int(float(v))
            except Exception:
                return 0

        def f(v):
            try:
                return float(v)
            except Exception:
                return 0.0

        vals.update({
            'impressions': n((insights_json or {}).get('impressions', 0)),
            'reach': n((insights_json or {}).get('reach', 0)),
            'clicks': n((insights_json or {}).get('clicks', 0)),
            'unique_clicks': n((insights_json or {}).get('unique_clicks', 0)),
            'ctr': f((insights_json or {}).get('ctr', 0)),
            'unique_ctr': f((insights_json or {}).get('unique_ctr', 0)),
            'cpc': f((insights_json or {}).get('cpc', 0)),
            'cpm': f((insights_json or {}).get('cpm', 0)),
            'spend': f((insights_json or {}).get('spend', 0)),
        })

        existing = self.search([('fb_ad_id', '=', fb_id)], limit=1)
        if existing:
            existing.write(vals)
            _logger.info("Updated ad %s", fb_id)
        else:
            vals['social_campaign_id'] = False
            self.create(vals)
            _logger.info("Created ad %s", fb_id)

    @api.model
    def _cron_sync_all_accounts(self):
        """Find social.campaign records that have meta credentials and sync them."""
        SocialCampaign = self.env['social.campaign']
        campaigns = SocialCampaign.search([('meta_ad_account_id', '!=', False)])
        for c in campaigns:
            try:
                # call our core fetch using account + token
                self._fetch_and_update_ads(c.meta_ad_account_id, access_token=c.meta_access_token)
            except Exception as e:
                _logger.exception("cron sync error for campaign %s: %s", c.id, e)


class AdsInsight(models.Model):
    _name = "ads.insight"
    _description = "Historical ad insight (per period)"

    ad_id = fields.Many2one('ads.ad', string="Ad", ondelete='cascade', required=True)
    date_start = fields.Date()
    date_stop = fields.Date()
    impressions = fields.Integer()
    reach = fields.Integer()
    clicks = fields.Integer()
    ctr = fields.Float()
    cpc = fields.Float()
    cpm = fields.Float()
    spend = fields.Float()
    actions_json = fields.Text()
