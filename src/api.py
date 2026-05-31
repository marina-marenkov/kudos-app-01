from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from src import models


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


app = FastAPI(title="Kudos API")


@app.on_event("startup")
def startup_event() -> None:
    init_fn = _resolve_callable("init_db", "initialize_db")
    _call_noargs(init_fn)


@app.post("/kudos", response_model=GiveKudosResponse, status_code=201)
def give_kudos(payload: GiveKudosRequest) -> GiveKudosResponse:
    give_fn = _resolve_callable("give_kudos", "create_kudos", "add_kudos")
    created = _call_give_kudos(give_fn, payload)
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
