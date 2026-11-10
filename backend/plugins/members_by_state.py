"""Provides state-level membership distribution for approved profiles."""
import typing
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.plugin_api import get_readonly_session
from app.public_views import PublicProfile

router = APIRouter(prefix="/v1/plugins/members_by_state", tags=["plugin:members_by_state"])


class StateCountItem(BaseModel):
    state: str = Field(description="State code or name, or Unknown if unassigned")
    count: int = Field(description="Number of approved members")


class StateCountsResponse(BaseModel):
    total_approved_members: int = Field(description="Total approved members across all states")
    total_states: int = Field(description="Total distinct states represented")
    items: typing.List[StateCountItem] = Field(description="List of states with counts")


def aggregate_state_counts(raw_rows: typing.List[typing.Tuple[typing.Optional[str], int]]) -> typing.List[dict]:
    counts: typing.Dict[str, int] = {}
    for state, count in raw_rows:
        state_name = state.strip() if state and state.strip() else "Unknown"
        counts[state_name] = counts.get(state_name, 0) + count
    results = [{"state": k, "count": v} for k, v in counts.items()]
    results.sort(key=lambda item: (-item["count"], item["state"]))
    return results


def summarize_state_data(items: typing.List[dict]) -> dict:
    total_members = sum(item["count"] for item in items)
    total_states = len([item for item in items if item["state"] != "Unknown"])
    return {
        "total_approved_members": total_members,
        "total_states": total_states,
        "items": items,
    }


@router.get("", response_model=StateCountsResponse)
async def get_members_by_state(
    session: AsyncSession = Depends(get_readonly_session),
) -> StateCountsResponse:
    query = (
        select(PublicProfile.state, func.count(PublicProfile.id))
        .group_by(PublicProfile.state)
    )
    result = await session.execute(query)
    raw_rows = result.all()
    items = aggregate_state_counts([(row[0], row[1]) for row in raw_rows])
    summary = summarize_state_data(items)
    return StateCountsResponse(**summary)
