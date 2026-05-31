from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable
from urllib import request

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from src import models

WEBHOOK_URL_ENV_VAR = "WEBHOOK_URL"
logger = logging.getLogger(__name__)


class GiveKudosRequest(BaseModel):
    from_user: str = Field(..., min_length=1)
    to_user: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    category: str = Field(default="general", min_length=1)


class GiveKudosResponse(BaseModel):
    kudos: dict[str, Any]


class UserKudosResponse(BaseModel):
    user: str
    kudos: list[dict[str, Any]]


class LeaderboardResponse(BaseModel):
    leaderboard: list[dict[str, Any]]


class RecentKudosResponse(BaseModel):
    recent: list[dict[str, Any]]


def _resolve_callable(*names: str) -> Callable[..., Any]:
    for name in names:
        fn = getattr(models, name, None)
        if callable(fn):
            return fn
    raise RuntimeError(f"None of expected models functions are available: {names}")


def _call_give_kudos(fn: Callable[..., Any], req: GiveKudosRequest) -> Any:
    call_attempts = (
        lambda: fn(
            from_user=req.from_user,
            to_user=req.to_user,
            message=req.message,
            category=req.category,
        ),
        lambda: fn(
            sender=req.from_user,
            receiver=req.to_user,
            message=req.message,
            category=req.category,
        ),
        lambda: fn(req.from_user, req.to_user, req.message, req.category),
    )
    for attempt in call_attempts:
        try:
            return attempt()
        except TypeError:
            continue
    raise HTTPException(status_code=500, detail="Failed to call models give kudos function")


def _call_with_user_arg(fn: Callable[..., Any], user: str) -> Any:
    call_attempts = (
        lambda: fn(user=user),
        lambda: fn(username=user),
        lambda: fn(user),
    )
    for attempt in call_attempts:
        try:
            return attempt()
        except TypeError:
            continue
    raise HTTPException(status_code=500, detail="Failed to call models user-based function")


def _call_noargs(fn: Callable[..., Any]) -> Any:
    try:
        return fn()
    except TypeError as exc:
        raise HTTPException(status_code=500, detail="Failed to call models no-arg function") from exc


def _build_webhook_card(payload: GiveKudosRequest) -> dict[str, Any]:
    return {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": f"{payload.from_user} sent kudos to {payload.to_user}",
        "text": (
            f"🎉 **{payload.from_user}** sent kudos to **{payload.to_user}**\n\n"
            f"**Category:** {payload.category}\n\n"
            f"**Message:** {payload.message}"
        ),
        "sections": [
            {
                "facts": [
                    {"name": "Sender", "value": payload.from_user},
                    {"name": "Receiver", "value": payload.to_user},
                    {"name": "Category", "value": payload.category},
                    {"name": "Message", "value": payload.message},
                ]
            }
        ],
    }


def _send_webhook_notification(payload: GiveKudosRequest) -> None:
    webhook_url = os.getenv(WEBHOOK_URL_ENV_VAR)
    if not webhook_url:
        return

    body = json.dumps(_build_webhook_card(payload)).encode("utf-8")
    webhook_request = request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        response = request.urlopen(webhook_request, timeout=5)
        close = getattr(response, "close", None)
        if callable(close):
            close()
    except Exception:
        logger.exception("Failed to send kudos webhook notification")


app = FastAPI(title="Kudos API")


@app.on_event("startup")
def startup_event() -> None:
    init_fn = _resolve_callable("init_db", "initialize_db")
    _call_noargs(init_fn)


@app.post("/kudos", response_model=GiveKudosResponse, status_code=201)
def give_kudos(payload: GiveKudosRequest) -> GiveKudosResponse:
    give_fn = _resolve_callable("give_kudos", "create_kudos", "add_kudos")
    created = _call_give_kudos(give_fn, payload)
    _send_webhook_notification(payload)
    return GiveKudosResponse(kudos=jsonable_encoder(created))


@app.get("/kudos/{user}", response_model=UserKudosResponse)
def get_user_kudos(user: str) -> UserKudosResponse:
    fetch_fn = _resolve_callable(
        "get_kudos_for_user",
        "fetch_kudos_for_user",
        "list_kudos_for_user",
        "get_user_kudos",
    )
    kudos = _call_with_user_arg(fetch_fn, user)
    return UserKudosResponse(user=user, kudos=jsonable_encoder(kudos))


@app.get("/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard() -> LeaderboardResponse:
    leaderboard_fn = _resolve_callable("get_leaderboard", "list_leaderboard")
    leaderboard = _call_noargs(leaderboard_fn)
    return LeaderboardResponse(leaderboard=jsonable_encoder(leaderboard))


@app.get("/recent", response_model=RecentKudosResponse)
def get_recent() -> RecentKudosResponse:
    recent_fn = _resolve_callable("get_recent", "get_recent_kudos", "list_recent_kudos", "get_recent_feed")
    recent = _call_noargs(recent_fn)
    return RecentKudosResponse(recent=jsonable_encoder(recent))
