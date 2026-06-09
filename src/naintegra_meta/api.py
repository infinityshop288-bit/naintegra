"""API FastAPI — dashboard Meta @delegadoluizcarlos."""

from __future__ import annotations

from typing import Any

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from naintegra_meta.auth import AuthUser, get_bearer_token, require_delegado_user
from naintegra_meta.ai_providers import list_provider_statuses, resolve_provider_settings
from naintegra_meta.content_ai import generate_content_ideas
from naintegra_meta.content_calendar import calendar_summary
from naintegra_meta.content_package import GENERATED_ROOT, compare_all_providers, generate_content_package
from naintegra_meta.image_providers import list_image_provider_statuses
from naintegra_meta.marketing_library import library_status
from naintegra_meta.marketing_data import AUTOMATION_HYPOTHESES, COMPETITORS, POSITIONING, ZAMBONI_STYLE
from naintegra_meta.pipeline import run_content_pipeline
from naintegra_meta.zamboni_style import ZAMBONI_BENCHMARK
from naintegra_meta.meta_client import InstagramFacebook, MetaAds, MetaApiError, MetaClient
from naintegra_meta.meta_permissions import permissions_report, setup_links
from naintegra_meta.settings import MetaSettings
from naintegra_meta.store import DelegadoStore
from naintegra_meta.token_sync import verify_pairing

_settings_singleton = MetaSettings()

app = FastAPI(
    title="NaIntegra — Dashboard @delegadoluizcarlos",
    version="0.1.0",
    description="Automação de conteúdo, publicação e monitoramento Instagram/Meta",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings_singleton.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _settings() -> MetaSettings:
    return _settings_singleton


class IdeasRequest(BaseModel):
    tema: str = Field(min_length=3, max_length=500)
    formato: str = Field(default="carrossel", pattern="^(carrossel|reels|story)$")
    provider: str | None = None


class PipelineRequest(BaseModel):
    days: int = Field(default=1, ge=1, le=31)
    start_date: str | None = None
    month: str | None = None
    provider: str | None = None
    dry_run: bool = False


class PackageRequest(BaseModel):
    tema: str = Field(min_length=3, max_length=500)
    formato: str = Field(default="carrossel", pattern="^(carrossel|reels|story)$")
    text_provider: str | None = None
    image_provider: str | None = None
    discipline: str | None = None
    use_ai_images: bool = True
    save_queue: bool = False


class QueueItem(BaseModel):
    id: str | None = None
    titulo: str
    formato: str = "carrossel"
    legenda: str = ""
    hashtags: list[str] = Field(default_factory=list)
    media_url: str | None = None
    scheduled_at: str | None = None
    status: str = Field(
        default="rascunho",
        pattern="^(rascunho|aguardando_aprovacao|aprovado|agendado|publicado|rejeitado)$",
    )
    meta: dict[str, Any] = Field(default_factory=dict)


class QueueStatusRequest(BaseModel):
    status: str = Field(
        pattern="^(rascunho|aguardando_aprovacao|aprovado|agendado|publicado|rejeitado)$"
    )


class PublishRequest(BaseModel):
    image_url: str
    caption: str


class ReelsPublishRequest(BaseModel):
    video_url: str
    caption: str


class AutomationStatusRequest(BaseModel):
    status: str = Field(pattern="^(ativo|pausado)$")


def _meta_client(settings: MetaSettings) -> MetaClient:
    if not settings.meta_access_token:
        raise HTTPException(503, "META_ACCESS_TOKEN não configurado")
    return MetaClient(settings.meta_access_token)


def _ig(settings: MetaSettings) -> InstagramFacebook:
    if not settings.ig_user_id:
        raise HTTPException(503, "IG_USER_ID não configurado")
    return InstagramFacebook(
        _meta_client(settings),
        ig_user_id=settings.ig_user_id,
        fb_page_id=settings.fb_page_id,
    )


def _ads(settings: MetaSettings) -> MetaAds:
    if not settings.meta_ad_account_id:
        raise HTTPException(503, "META_AD_ACCOUNT_ID não configurado")
    return MetaAds(_meta_client(settings), ad_account_id=settings.meta_ad_account_id)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/auth/me")
def auth_me(user: AuthUser = Depends(require_delegado_user)) -> dict[str, str]:
    return {"id": user.id, "email": user.email}


@app.get("/meta/pairing")
def meta_pairing(user: AuthUser = Depends(require_delegado_user)) -> dict[str, Any]:
    del user
    settings = _settings_singleton
    result = verify_pairing(settings)
    return {"paired": result.get("valid"), "checks": result.get("checks"), "ids": {
        "fb_page_id": settings.fb_page_id,
        "ig_user_id": settings.ig_user_id,
    }}


@app.get("/meta/debug-token")
def debug_token(
    user: AuthUser = Depends(require_delegado_user),
    settings: MetaSettings = Depends(_settings),
) -> dict[str, Any]:
    del user
    try:
        return _meta_client(settings).debug_token()
    except MetaApiError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.get("/overview")
def overview(
    user: AuthUser = Depends(require_delegado_user),
    settings: MetaSettings = Depends(_settings),
) -> dict[str, Any]:
    del user
    result: dict[str, Any] = {
        "positioning": POSITIONING,
        "kpis": {
            "seguidores": None,
            "engajamento": None,
            "alcance": None,
            "leads": None,
            "fonte": "aguardando_api",
        },
    }
    if not settings.meta_access_token or not settings.ig_user_id:
        return result
    try:
        profile = _ig(settings).profile()
        ig = _ig(settings)
        result["profile"] = profile
        result["kpis"]["seguidores"] = profile.get("followers_count")
        try:
            insights = ig.account_insights(period="day")
            result["insights"] = insights
            result["kpis"]["fonte"] = "graph_api"
            metric_map = _flatten_insights(insights)
            result["kpis"]["alcance"] = metric_map.get("reach") or metric_map.get("profile_views")
            summary = ig.media_engagement_summary(limit=10)
            result["media_summary"] = summary
            result["kpis"]["engajamento"] = summary.get("total_interactions") or metric_map.get(
                "profile_views"
            )
        except MetaApiError as exc:
            result["insights_error"] = str(exc)
            _apply_media_fallback(result, ig)
    except MetaApiError as exc:
        result["error"] = str(exc)
    return result


def _flatten_insights(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in payload.get("data") or []:
        name = item.get("name")
        values = item.get("values") or []
        if name and values:
            out[name] = values[-1].get("value")
    return out


def _apply_media_fallback(result: dict[str, Any], ig: InstagramFacebook) -> None:
    summary = ig.media_engagement_summary(limit=10)
    result["media_summary"] = summary
    result["kpis"]["engajamento"] = summary.get("total_interactions")
    result["kpis"]["alcance"] = result["kpis"].get("alcance") or summary.get("avg_interactions_per_post")
    if result["kpis"].get("fonte") != "graph_api":
        result["kpis"]["fonte"] = "media_api"
    result.setdefault("warnings", []).append(
        "Insights oficiais indisponíveis — usando curtidas/comentários dos últimos posts. "
        "Reautorize com instagram_manage_insights para alcance real."
    )


@app.get("/content/providers")
def content_providers(user: AuthUser = Depends(require_delegado_user)) -> dict[str, Any]:
    del user
    cfg = resolve_provider_settings()
    return {
        "active": cfg["provider"],
        "providers": [
            {
                "id": p.id,
                "label": p.label,
                "configured": p.configured,
                "model": p.model_current,
                "detail": p.detail,
            }
            for p in list_provider_statuses()
        ],
    }


@app.get("/content/calendar")
def content_calendar(
    month: str | None = None,
    user: AuthUser = Depends(require_delegado_user),
) -> dict[str, Any]:
    del user
    try:
        return {"calendar": calendar_summary(month), "style": ZAMBONI_STYLE}
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/content/ideas")
def content_ideas(
    body: IdeasRequest,
    user: AuthUser = Depends(require_delegado_user),
    settings: MetaSettings = Depends(_settings),
) -> dict[str, Any]:
    del user
    try:
        ideas, source = generate_content_ideas(
            body.tema,
            body.formato,
            settings=settings,
            provider=body.provider,  # type: ignore[arg-type]
        )
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"ideas": ideas, "source": source}


@app.get("/content/marketing-library")
def content_marketing_library(user: AuthUser = Depends(require_delegado_user)) -> dict[str, Any]:
    del user
    return library_status()


@app.get("/content/image-providers")
def content_image_providers(user: AuthUser = Depends(require_delegado_user)) -> dict[str, Any]:
    del user
    return {
        "providers": [s.__dict__ for s in list_image_provider_statuses()],
    }


@app.post("/content/package/generate")
async def content_package_generate(
    body: PackageRequest,
    jwt: str = Depends(get_bearer_token),
    user: AuthUser = Depends(require_delegado_user),
    settings: MetaSettings = Depends(_settings),
) -> dict[str, Any]:
    del user
    try:
        item = generate_content_package(
            tema=body.tema,
            formato=body.formato,
            text_provider=body.text_provider,  # type: ignore[arg-type]
            image_provider=body.image_provider,  # type: ignore[arg-type]
            discipline=body.discipline,
            use_ai_images=body.use_ai_images,
        )
    except Exception as exc:
        raise HTTPException(
            503,
            f"Falha ao gerar pacote: {exc}. Verifique Ollama/API ou desmarque imagens IA.",
        ) from exc

    assets = item.get("assets") or []
    if assets:
        item["media_url"] = assets[0].get("url")

    if body.save_queue:
        store = DelegadoStore(settings)
        queue_row = {
            "titulo": item["titulo"],
            "formato": item["formato"],
            "legenda": item["legenda"],
            "hashtags": item.get("hashtags") or [],
            "media_url": item.get("media_url"),
            "status": item.get("status", "aguardando_aprovacao"),
            "meta": item.get("meta") or {},
        }
        try:
            saved = store.upsert_queue_item_service(queue_row)
            item["queue_id"] = saved.get("id")
        except Exception as exc:
            item["queue_error"] = str(exc)[:500]

    return {"package": item}


@app.post("/content/package/compare")
def content_package_compare(
    body: IdeasRequest,
    user: AuthUser = Depends(require_delegado_user),
) -> dict[str, Any]:
    del user
    return compare_all_providers(body.tema, body.formato)


@app.get("/content/assets/{package_id}/{file_path:path}")
def content_asset(
    package_id: str,
    file_path: str,
    user: AuthUser = Depends(require_delegado_user),
) -> FileResponse:
    del user
    if not package_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(400, "package_id inválido")
    root = (GENERATED_ROOT / package_id).resolve()
    target = (root / file_path).resolve()
    if not str(target).startswith(str(GENERATED_ROOT.resolve())):
        raise HTTPException(403, "path negado")
    if not target.is_file():
        raise HTTPException(404, "arquivo não encontrado")
    return FileResponse(target)


@app.post("/content/pipeline/run")
def content_pipeline_run(
    body: PipelineRequest,
    user: AuthUser = Depends(require_delegado_user),
) -> dict[str, Any]:
    del user
    from datetime import date as date_cls

    start = date_cls.fromisoformat(body.start_date) if body.start_date else None
    return run_content_pipeline(
        days=body.days,
        start_date=start,
        month=body.month,
        provider=body.provider,  # type: ignore[arg-type]
        dry_run=body.dry_run,
    )


@app.patch("/content/queue/{item_id}/status")
async def patch_queue_status(
    item_id: str,
    body: QueueStatusRequest,
    jwt: str = Depends(get_bearer_token),
    user: AuthUser = Depends(require_delegado_user),
    settings: MetaSettings = Depends(_settings),
) -> dict[str, Any]:
    del user
    store = DelegadoStore(settings)
    items = await store.list_queue(user_jwt=jwt)
    row = next((i for i in items if str(i.get("id")) == item_id), None)
    if not row:
        raise HTTPException(404, "Item não encontrado")
    row["status"] = body.status
    return await store.upsert_queue_item(user_jwt=jwt, item=row)


@app.get("/content/queue")
async def get_queue(
    jwt: str = Depends(get_bearer_token),
    user: AuthUser = Depends(require_delegado_user),
    settings: MetaSettings = Depends(_settings),
) -> dict[str, Any]:
    del user
    store = DelegadoStore(settings)
    items = await store.list_queue(user_jwt=jwt)
    return {"items": items}


@app.post("/content/queue")
async def save_queue_item(
    body: QueueItem,
    jwt: str = Depends(get_bearer_token),
    user: AuthUser = Depends(require_delegado_user),
    settings: MetaSettings = Depends(_settings),
) -> dict[str, Any]:
    del user
    store = DelegadoStore(settings)
    return await store.upsert_queue_item(
        user_jwt=jwt,
        item=body.model_dump(exclude_none=True),
    )


@app.delete("/content/queue/{item_id}")
async def remove_queue_item(
    item_id: str,
    jwt: str = Depends(get_bearer_token),
    user: AuthUser = Depends(require_delegado_user),
    settings: MetaSettings = Depends(_settings),
) -> dict[str, str]:
    del user
    store = DelegadoStore(settings)
    await store.delete_queue_item(user_jwt=jwt, item_id=item_id)
    return {"status": "deleted", "id": item_id}


@app.post("/publish/image")
def publish_image(
    body: PublishRequest,
    user: AuthUser = Depends(require_delegado_user),
    settings: MetaSettings = Depends(_settings),
) -> dict[str, Any]:
    del user
    try:
        return _ig(settings).publish_image(body.image_url, body.caption)
    except MetaApiError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/publish/reels")
def publish_reels(
    body: ReelsPublishRequest,
    user: AuthUser = Depends(require_delegado_user),
    settings: MetaSettings = Depends(_settings),
) -> dict[str, Any]:
    del user
    try:
        return _ig(settings).publish_reels(body.video_url, body.caption)
    except MetaApiError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.get("/ads/campaigns")
def ads_campaigns(
    user: AuthUser = Depends(require_delegado_user),
    settings: MetaSettings = Depends(_settings),
) -> dict[str, Any]:
    del user
    ads = _ads(settings)
    links = setup_links(settings)
    try:
        ads.probe_access()
    except MetaApiError as exc:
        return {
            "campaigns": {"data": []},
            "account_insights": {"data": []},
            "ads_blocked": True,
            "error": str(exc),
            "setup_links": links,
            "hint": (
                "Autorize o app Claude na conta de anúncios no Business Manager "
                "(ads_read / ads_management)."
            ),
        }
    try:
        campaigns = ads.list_campaigns()
        insights = ads.account_insights()
        return {"campaigns": campaigns, "account_insights": insights, "setup_links": links}
    except MetaApiError as exc:
        return {
            "campaigns": {"data": []},
            "account_insights": {"data": []},
            "ads_blocked": True,
            "error": str(exc),
            "setup_links": links,
        }


@app.get("/meta/permissions")
def meta_permissions(
    user: AuthUser = Depends(require_delegado_user),
    settings: MetaSettings = Depends(_settings),
) -> dict[str, Any]:
    del user
    return permissions_report(settings)


@app.get("/monitoring/insights")
def monitoring_insights(
    user: AuthUser = Depends(require_delegado_user),
    settings: MetaSettings = Depends(_settings),
) -> dict[str, Any]:
    del user
    ig = _ig(settings)
    media = ig.media_list(limit=10)
    summary = ig.media_engagement_summary(limit=10)
    payload: dict[str, Any] = {
        "recent_media": media,
        "derived_metrics": summary,
        "setup_links": setup_links(settings),
    }
    try:
        payload["account_insights"] = ig.account_insights(period="day")
        payload["insights_source"] = "graph_api"
    except MetaApiError as exc:
        payload["account_insights"] = {"data": []}
        payload["insights_error"] = str(exc)
        payload["insights_source"] = "media_api"
        payload["warning"] = (
            "Permissão instagram_manage_insights ausente — exibindo engajamento dos posts recentes."
        )
    return payload


@app.get("/monitoring/comments/{media_id}")
def monitoring_comments(
    media_id: str,
    user: AuthUser = Depends(require_delegado_user),
    settings: MetaSettings = Depends(_settings),
) -> dict[str, Any]:
    del user
    try:
        return _ig(settings).comments(media_id)
    except MetaApiError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.get("/competitors")
def competitors(user: AuthUser = Depends(require_delegado_user)) -> dict[str, Any]:
    del user
    return {
        "competitors": COMPETITORS,
        "positioning": POSITIONING,
        "zamboni_benchmark": ZAMBONI_BENCHMARK,
        "zamboni_style": ZAMBONI_STYLE,
    }


@app.get("/automations")
async def list_automations(
    jwt: str = Depends(get_bearer_token),
    user: AuthUser = Depends(require_delegado_user),
    settings: MetaSettings = Depends(_settings),
) -> dict[str, Any]:
    del user
    store = DelegadoStore(settings)
    db_items = await store.list_automations(user_jwt=jwt)
    by_id = {row["id"]: row for row in db_items}
    merged = []
    for hypo in AUTOMATION_HYPOTHESES:
        row = by_id.get(hypo["id"], {})
        merged.append({**hypo, "status": row.get("status", hypo["status_default"])})
    return {"automations": merged}


@app.patch("/automations/{automation_id}")
async def patch_automation(
    automation_id: str,
    body: AutomationStatusRequest,
    jwt: str = Depends(get_bearer_token),
    user: AuthUser = Depends(require_delegado_user),
    settings: MetaSettings = Depends(_settings),
) -> dict[str, Any]:
    del user
    store = DelegadoStore(settings)
    return await store.set_automation_status(jwt, automation_id, body.status)


def main() -> None:
    import uvicorn

    uvicorn.run(
        "naintegra_meta.api:app",
        host="0.0.0.0",
        port=int(__import__("os").environ.get("DELEGADO_API_PORT", "8787")),
        reload=False,
    )
