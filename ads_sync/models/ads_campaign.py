# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import requests
except Exception:
    requests = None
    _logger.warning("requests library not available. HTTP calls will fail.")


class AdsCampaign(models.Model):
    _name = "ads.campaign"
    _description = "Ads Campaign (generic for multiple ad platforms)"
    _rec_name = "name"
    _order = "create_date desc"

    name = fields.Char(string="Name")
    platform = fields.Selection([
        ("facebook", "Facebook"),
        ("google", "Google"),
        ("other", "Other"),
    ], string="Platform", required=True, default="facebook")
    campaign_code = fields.Char(string="Campaign Code", required=True)
    ad_id = fields.Char(string="Ad ID", index=True)
    adset_name = fields.Char(string="AdSet / Adset Name")
    status = fields.Char(string="Status")
    budget_remaining = fields.Float(string="Budget Remaining")
    thumbnail_url = fields.Char(string="Thumbnail URL")
    impressions = fields.Integer(string="Impressions")
    reach = fields.Integer(string="Reach")
    clicks = fields.Integer(string="Clicks")
    ctr = fields.Float(string="CTR")
    cpc = fields.Float(string="CPC")
    cpm = fields.Float(string="CPM")
    spend = fields.Float(string="Spend")
    objective = fields.Char(string="Objective")
    actions_json = fields.Text(string="Actions (JSON)")
    date_start = fields.Date(string="Insight Date Start")
    date_stop = fields.Date(string="Insight Date Stop")
    created_time_raw = fields.Char(string="Created Time (raw)")
    updated_time_raw = fields.Char(string="Updated Time (raw)")

    _sql_constraints = [
        ("campaign_code_unique", "UNIQUE(campaign_code)", "Campaign Code must be unique across platforms"),
    ]

    @api.model
    def _build_campaign_code(self, platform, ad_id, campaign_name=None):
        # deterministic unique code for cross-platform mapping
        # pattern: <platform>_<ad_id>
        if not platform or not ad_id:
            # fallback use name hash if missing
            base = (campaign_name or "campaign").replace(" ", "_")
            import hashlib
            h = hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]
            return "%s_%s" % (platform or "other", h)
        return "%s_%s" % (platform, ad_id)

    @api.model
    def _facebook_fetch_ads(self, ad_account_id, access_token, limit=100):
        """Return parsed list of ad dicts from Facebook Graph API. Minimal pagination support (single page)."""
        if requests is None:
            raise UserError(_("Python 'requests' library is required on the server to call Facebook API."))

        if not ad_account_id:
            raise UserError(_("Ad Account ID is required."))

        # Accept either form: act_123 or 123
        ad_acc = str(ad_account_id)
        if not ad_acc.startswith("act_"):
            ad_acc = "act_%s" % ad_acc

        base = "https://graph.facebook.com/v24.0/%s/ads" % ad_acc
        fields = ",".join([
            "id",
            "name",
            "status",
            "adset{id,name,daily_budget,lifetime_budget,budget_remaining}",
            "campaign_name",
            "created_time",
            "updated_time",
            "creative{effective_object_story_id,object_story_spec{link_data{link,message,name,caption,description}},image_url,thumbnail_url,video_id}",
            "insights{impressions,reach,clicks,ctr,cpc,cpm,spend,objective,actions,inline_link_clicks,inline_post_engagement,unique_clicks,unique_ctr,date_start,date_stop}"
        ])
        params = {
            "fields": fields,
            "limit": limit,
            "access_token": access_token,
        }
        resp = requests.get(base, params=params, timeout=30)
        if resp.status_code != 200:
            _logger.error("Facebook API error: %s - %s", resp.status_code, resp.text)
            raise UserError(_("Facebook API error: %s\n%s") % (resp.status_code, resp.text))

        data = resp.json()
        results = []

        for ad in data.get("data", []):
            parsed = {
                "ad_id": ad.get("id"),
                "name": ad.get("name"),
                "status": ad.get("status"),
                "adset_name": None,
                "budget_remaining": None,
                "campaign_name": ad.get("campaign_name"),
                "created_time_raw": ad.get("created_time"),
                "updated_time_raw": ad.get("updated_time"),
                "thumbnail_url": None,
                "impressions": None,
                "reach": None,
                "clicks": None,
                "ctr": None,
                "cpc": None,
                "cpm": None,
                "spend": None,
                "objective": None,
                "actions_json": None,
                "date_start": None,
                "date_stop": None,
            }
            adset = ad.get("adset") or {}
            parsed["adset_name"] = adset.get("name")
            # budgets might be string or numeric
            try:
                parsed["budget_remaining"] = float(adset.get("budget_remaining")) if adset.get("budget_remaining") else None
            except Exception:
                parsed["budget_remaining"] = None

            creative = ad.get("creative") or {}
            parsed["thumbnail_url"] = creative.get("thumbnail_url") or creative.get("image_url")

            insights = ad.get("insights") or {}
            insights_data = insights.get("data") or []
            if insights_data:
                ins = insights_data[0]
                # numeric fields often returned as strings
                def to_int(val):
                    try:
                        return int(val)
                    except Exception:
                        try:
                            return int(float(val))
                        except Exception:
                            return None

                def to_float(val):
                    try:
                        return float(val)
                    except Exception:
                        return None

                parsed["impressions"] = to_int(ins.get("impressions"))
                parsed["reach"] = to_int(ins.get("reach"))
                parsed["clicks"] = to_int(ins.get("clicks"))
                parsed["ctr"] = to_float(ins.get("ctr"))
                parsed["cpc"] = to_float(ins.get("cpc"))
                parsed["cpm"] = to_float(ins.get("cpm"))
                parsed["spend"] = to_float(ins.get("spend"))
                parsed["objective"] = ins.get("objective")
                parsed["actions_json"] = json.dumps(ins.get("actions")) if ins.get("actions") else None
                parsed["date_start"] = ins.get("date_start")
                parsed["date_stop"] = ins.get("date_stop")

            results.append(parsed)

        # NOTE: pagination not fully implemented (could use data['paging']['next']). For first version we import only first page.
        return results

    def sync_from_facebook(self, ad_account_id=None, access_token=None):
        """Public method to do upsert from facebook data.
           Returns dict with counts.
        """
        # use sudo to be safe for reading system params
        icp = self.env["ir.config_parameter"].sudo()
        ad_account_id = ad_account_id or icp.get_param("meta.ad_account_id")
        access_token = access_token or icp.get_param("meta.access_token")
        if not ad_account_id or not access_token:
            raise UserError(_("Ad account ID and access token are required either in the form or system parameters."))

        ads_data = self._facebook_fetch_ads(ad_account_id, access_token)
        created = 0
        updated = 0

        for item in ads_data:
            campaign_code = self._build_campaign_code("facebook", item.get("ad_id"), item.get("campaign_name") or item.get("name"))

            # search existing by campaign_code
            existing = self.sudo().search([("campaign_code", "=", campaign_code)], limit=1)
            vals = {
                "name": item.get("name") or item.get("campaign_name"),
                "platform": "facebook",
                "campaign_code": campaign_code,
                "ad_id": item.get("ad_id"),
                "adset_name": item.get("adset_name"),
                "status": item.get("status"),
                "budget_remaining": item.get("budget_remaining"),
                "thumbnail_url": item.get("thumbnail_url"),
                "impressions": item.get("impressions"),
                "reach": item.get("reach"),
                "clicks": item.get("clicks"),
                "ctr": item.get("ctr"),
                "cpc": item.get("cpc"),
                "cpm": item.get("cpm"),
                "spend": item.get("spend"),
                "objective": item.get("objective"),
                "actions_json": item.get("actions_json"),
                "date_start": item.get("date_start"),
                "date_stop": item.get("date_stop"),
                "created_time_raw": item.get("created_time_raw"),
                "updated_time_raw": item.get("updated_time_raw"),
            }

            if existing:
                try:
                    existing.sudo().write(vals)
                    updated += 1
                except Exception as e:
                    _logger.exception("Error updating ad campaign %s: %s", campaign_code, e)
            else:
                try:
                    self.sudo().create(vals)
                    created += 1
                except Exception as e:
                    _logger.exception("Error creating ad campaign %s: %s", campaign_code, e)

        return {"created": created, "updated": updated}
