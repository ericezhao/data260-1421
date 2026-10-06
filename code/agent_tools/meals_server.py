"""MCP server "meals": four tools over the public TheMealDB API (test key 1).

Run with the MCP Inspector:  mcp dev code/agent_tools/meals_server.py
"""

import logging
import sys
from pathlib import Path
from typing import Annotated, Any

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
from retry import RetryExhausted, RetryPolicy, TransientError, call_with_retry  # noqa: E402

# STDIO servers must keep stdout clean for JSON-RPC, so all logs go to stderr
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("meals")

API_BASE = "https://www.themealdb.com/api/json/v1/1/"
POLICY = RetryPolicy(max_attempts=3, timeout_s=8.0, base_delay_s=0.5, max_delay_s=2.0)

mcp = FastMCP("meals")


def _get(endpoint: str, params: dict[str, Any] | None = None) -> list[dict] | None:
    """Return the "meals" list, or None when TheMealDB has no matches."""

    def request() -> dict:
        try:
            resp = httpx.get(API_BASE + endpoint, params=params, timeout=POLICY.timeout_s)
        except httpx.TransportError as exc:
            raise TransientError(f"network error: {exc}") from exc
        if resp.status_code >= 500:
            raise TransientError(f"TheMealDB returned HTTP {resp.status_code}")
        resp.raise_for_status()
        return resp.json()

    log.info("GET %s %s", endpoint, params or "")
    try:
        body = call_with_retry(request, POLICY)
    except RetryExhausted as exc:
        raise RuntimeError(f"TheMealDB is unreachable: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"TheMealDB request failed: HTTP {exc.response.status_code}") from exc
    except ValueError as exc:
        raise RuntimeError("TheMealDB returned invalid JSON") from exc
    return body.get("meals")


def _no_matches(what: str) -> dict:
    return {"results": [], "message": f"no matches for {what}"}


def _details(meal: dict) -> dict:
    ingredients = []
    for i in range(1, 21):
        name = (meal.get(f"strIngredient{i}") or "").strip()
        if name:
            ingredients.append({"name": name, "measure": (meal.get(f"strMeasure{i}") or "").strip()})
    return {
        "id": meal["idMeal"],
        "name": meal["strMeal"],
        "category": meal.get("strCategory"),
        "area": meal.get("strArea"),
        "instructions": meal.get("strInstructions"),
        "image": meal.get("strMealThumb"),
        "source": meal.get("strSource") or None,
        "youtube": meal.get("strYoutube") or None,
        "ingredients": ingredients,
    }


@mcp.tool()
def search_meals_by_name(
    query: Annotated[str, Field(min_length=1, description="Meal name or part of it, e.g. Arrabiata")],
    limit: Annotated[int, Field(ge=1, le=25)] = 5,
) -> list[dict] | dict:
    """Search meals by name. Returns up to `limit` meals with id, name, area, category, thumb."""
    meals = _get("search.php", {"s": query})
    if not meals:
        return _no_matches(f"name '{query}'")
    return [
        {
            "id": m["idMeal"],
            "name": m["strMeal"],
            "area": m.get("strArea"),
            "category": m.get("strCategory"),
            "thumb": m.get("strMealThumb"),
        }
        for m in meals[:limit]
    ]


@mcp.tool()
def meals_by_ingredient(
    ingredient: Annotated[str, Field(min_length=1, description="Main ingredient, e.g. chicken")],
    limit: Annotated[int, Field(ge=1, le=50)] = 12,
) -> list[dict] | dict:
    """List meals that use a main ingredient. Returns small cards: id, name, thumb."""
    meals = _get("filter.php", {"i": ingredient})
    if not meals:
        return _no_matches(f"ingredient '{ingredient}'")
    return [
        {"id": m["idMeal"], "name": m["strMeal"], "thumb": m.get("strMealThumb")}
        for m in meals[:limit]
    ]


@mcp.tool()
def random_meal() -> dict:
    """Return one random meal with full recipe details."""
    meals = _get("random.php")
    if not meals:
        return _no_matches("a random meal")
    return _details(meals[0])


@mcp.tool()
def meal_details(id: str | int) -> dict:
    """Look up one meal by its TheMealDB id and return the full recipe."""
    meals = _get("lookup.php", {"i": str(id).strip()})
    if not meals:
        return _no_matches(f"id {id}")
    return _details(meals[0])


if __name__ == "__main__":
    mcp.run(transport="stdio")
