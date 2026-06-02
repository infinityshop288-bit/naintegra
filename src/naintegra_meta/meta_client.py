"""Cliente unificado para Graph API do Meta (IG/FB, Ads, WhatsApp Cloud)."""

from __future__ import annotations

import time
from typing import Any

import httpx

API_VERSION = "v23.0"
GRAPH_BASE = f"https://graph.facebook.com/{API_VERSION}"


class MetaApiError(Exception):
    def __init__(self, message: str, *, status: int | None = None, payload: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.payload = payload


class MetaClient:
    def __init__(self, access_token: str, *, timeout: float = 60.0) -> None:
        self.access_token = access_token
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = path if path.startswith("http") else f"{GRAPH_BASE}/{path.lstrip('/')}"
        q = dict(params or {})
        q.setdefault("access_token", self.access_token)
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.request(method, url, params=q, json=json)
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text}
        if resp.status_code >= 400:
            err = body.get("error", {}) if isinstance(body, dict) else {}
            msg = err.get("message") if isinstance(err, dict) else str(body)
            raise MetaApiError(
                msg or f"Meta API HTTP {resp.status_code}",
                status=resp.status_code,
                payload=body,
            )
        if not isinstance(body, dict):
            return {"data": body}
        return body

    def debug_token(self, input_token: str | None = None) -> dict[str, Any]:
        token = input_token or self.access_token
        return self._request("GET", "debug_token", params={"input_token": token})

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        return self._request("GET", path, params=params)

    def post(self, path: str, **params: Any) -> dict[str, Any]:
        return self._request("POST", path, params=params)


class InstagramFacebook:
    def __init__(self, client: MetaClient, *, ig_user_id: str, fb_page_id: str | None = None) -> None:
        self.client = client
        self.ig_user_id = ig_user_id
        self.fb_page_id = fb_page_id

    def profile(self) -> dict[str, Any]:
        fields = "username,name,biography,followers_count,follows_count,media_count,profile_picture_url"
        return self.client.get(self.ig_user_id, fields=fields)

    def media_list(self, limit: int = 25) -> dict[str, Any]:
        fields = "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count"
        return self.client.get(f"{self.ig_user_id}/media", fields=fields, limit=limit)

    def media_engagement_summary(self, limit: int = 10) -> dict[str, Any]:
        """Métricas derivadas de posts recentes (não exige instagram_manage_insights)."""
        media = self.media_list(limit=limit).get("data") or []
        likes = 0
        comments = 0
        posts = len(media)
        for item in media:
            likes += int(item.get("like_count") or 0)
            comments += int(item.get("comments_count") or 0)
        interactions = likes + comments
        avg = round(interactions / posts, 1) if posts else 0.0
        rate = round((interactions / max(posts, 1)) * 100, 2)
        return {
            "posts_analyzed": posts,
            "total_likes": likes,
            "total_comments": comments,
            "total_interactions": interactions,
            "avg_interactions_per_post": avg,
            "engagement_rate_pct": rate,
            "recent_media": media,
            "source": "media_api",
        }

    def account_insights(self, period: str = "day", metrics: str | None = None) -> dict[str, Any]:
        if metrics:
            return self.client.get(
                f"{self.ig_user_id}/insights",
                metric=metrics,
                period=period,
            )

        merged: list[dict[str, Any]] = []
        for params in (
            {"metric": "reach,follower_count", "period": period},
            {"metric": "profile_views", "period": period, "metric_type": "total_value"},
        ):
            chunk = self.client.get(f"{self.ig_user_id}/insights", **params)
            merged.extend(chunk.get("data") or [])
        return {"data": merged}

    def media_insights(self, media_id: str) -> dict[str, Any]:
        metrics = "reach,saved,shares,total_interactions,views"
        return self.client.get(f"{media_id}/insights", metric=metrics)

    def create_image_container(self, image_url: str, caption: str) -> dict[str, Any]:
        return self.client.post(
            f"{self.ig_user_id}/media",
            image_url=image_url,
            caption=caption,
        )

    def create_carousel_container(self, children_ids: list[str], caption: str) -> dict[str, Any]:
        return self.client.post(
            f"{self.ig_user_id}/media",
            media_type="CAROUSEL",
            children=",".join(children_ids),
            caption=caption,
        )

    def create_reels_container(self, video_url: str, caption: str) -> dict[str, Any]:
        return self.client.post(
            f"{self.ig_user_id}/media",
            media_type="REELS",
            video_url=video_url,
            caption=caption,
        )

    def publish_container(self, creation_id: str) -> dict[str, Any]:
        return self.client.post(f"{self.ig_user_id}/media_publish", creation_id=creation_id)

    def publish_image(self, image_url: str, caption: str) -> dict[str, Any]:
        container = self.create_image_container(image_url, caption)
        creation_id = container.get("id")
        if not creation_id:
            raise MetaApiError("Container sem id", payload=container)
        return self.publish_container(creation_id)

    def publish_reels(self, video_url: str, caption: str, *, max_wait: int = 120) -> dict[str, Any]:
        container = self.create_reels_container(video_url, caption)
        creation_id = container.get("id")
        if not creation_id:
            raise MetaApiError("Container Reels sem id", payload=container)
        deadline = time.time() + max_wait
        while time.time() < deadline:
            status = self.client.get(creation_id, fields="status_code")
            code = status.get("status_code")
            if code == "FINISHED":
                return self.publish_container(creation_id)
            if code == "ERROR":
                raise MetaApiError("Processamento Reels falhou", payload=status)
            time.sleep(5)
        raise MetaApiError("Timeout aguardando processamento do Reels")

    def publish_facebook_page_post(self, message: str, link: str | None = None) -> dict[str, Any]:
        if not self.fb_page_id:
            raise MetaApiError("FB_PAGE_ID não configurado")
        params: dict[str, Any] = {"message": message}
        if link:
            params["link"] = link
        return self.client.post(f"{self.fb_page_id}/feed", **params)

    def comments(self, media_id: str, limit: int = 50) -> dict[str, Any]:
        fields = "id,text,timestamp,username,like_count,replies{id,text,username}"
        return self.client.get(f"{media_id}/comments", fields=fields, limit=limit)

    def reply_comment(self, comment_id: str, message: str) -> dict[str, Any]:
        return self.client.post(f"{comment_id}/replies", message=message)


class MetaAds:
    def __init__(self, client: MetaClient, *, ad_account_id: str) -> None:
        self.client = client
        self.ad_account_id = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"

    def list_campaigns(self, limit: int = 25) -> dict[str, Any]:
        fields = "id,name,status,objective,daily_budget,lifetime_budget,start_time,stop_time"
        return self.client.get(f"{self.ad_account_id}/campaigns", fields=fields, limit=limit)

    def probe_access(self) -> dict[str, Any]:
        """Verifica se a conta de anúncios autorizou o app."""
        return self.client.get(
            self.ad_account_id,
            fields="id,name,account_status,currency,business",
        )

    def account_insights(
        self,
        *,
        date_preset: str = "last_30d",
        level: str = "account",
    ) -> dict[str, Any]:
        fields = "spend,impressions,clicks,ctr,reach,cpc,cpm,actions,cost_per_action_type"
        return self.client.get(
            f"{self.ad_account_id}/insights",
            fields=fields,
            date_preset=date_preset,
            level=level,
        )

    def campaign_insights(self, campaign_id: str, *, date_preset: str = "last_30d") -> dict[str, Any]:
        fields = "campaign_name,spend,impressions,clicks,ctr,reach,actions,cost_per_action_type"
        return self.client.get(
            f"{campaign_id}/insights",
            fields=fields,
            date_preset=date_preset,
        )


class WhatsAppCloud:
    def __init__(self, token: str, *, phone_number_id: str) -> None:
        self.token = token
        self.phone_number_id = phone_number_id
        self.base = f"https://graph.facebook.com/{API_VERSION}/{phone_number_id}"

    def send_text(self, to: str, body: str) -> dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body},
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{self.base}/messages",
                json=payload,
                headers={"Authorization": f"Bearer {self.token}"},
            )
        body_json = resp.json()
        if resp.status_code >= 400:
            err = body_json.get("error", {}) if isinstance(body_json, dict) else {}
            raise MetaApiError(
                err.get("message", f"WhatsApp API HTTP {resp.status_code}"),
                status=resp.status_code,
                payload=body_json,
            )
        return body_json

    def send_template(self, to: str, template_name: str, language: str = "pt_BR") -> dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {"name": template_name, "language": {"code": language}},
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{self.base}/messages",
                json=payload,
                headers={"Authorization": f"Bearer {self.token}"},
            )
        body_json = resp.json()
        if resp.status_code >= 400:
            err = body_json.get("error", {}) if isinstance(body_json, dict) else {}
            raise MetaApiError(
                err.get("message", f"WhatsApp API HTTP {resp.status_code}"),
                status=resp.status_code,
                payload=body_json,
            )
        return body_json
