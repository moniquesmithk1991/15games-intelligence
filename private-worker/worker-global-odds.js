const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Content-Type": "application/json; charset=utf-8"
};

const API_BASE = "https://api.the-odds-api.com/v4";
const MAX_COMPETITIONS_PER_REFRESH = 10;
const REGIONS = "uk,eu,us2";
const DEFAULT_PRIORITY = [
  "soccer_epl",
  "soccer_spain_la_liga",
  "soccer_germany_bundesliga",
  "soccer_italy_serie_a",
  "soccer_uefa_champs_league",
  "soccer_france_ligue_one",
  "soccer_england_championship",
  "soccer_netherlands_eredivisie",
  "soccer_portugal_primeira_liga",
  "soccer_usa_mls"
];

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: CORS });
}

async function oddsApi(path, env) {
  if (!env.ODDS_API_KEY) throw new Error("ODDS_API_KEY secret is missing in Cloudflare.");
  const separator = path.includes("?") ? "&" : "?";
  const url = API_BASE + path + separator + "apiKey=" + encodeURIComponent(env.ODDS_API_KEY);
  const response = await fetch(url);
  const usage = {
    remaining: response.headers.get("x-requests-remaining"),
    used: response.headers.get("x-requests-used"),
    last: response.headers.get("x-requests-last")
  };
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.message || payload.error || ("Odds provider returned HTTP " + response.status));
    error.status = response.status;
    error.usage = usage;
    throw error;
  }
  return { payload, usage };
}

async function getSports(env) {
  const result = await oddsApi("/sports/", env);
  const competitions = (Array.isArray(result.payload) ? result.payload : [])
    .filter(item => item && item.key && item.key.startsWith("soccer_") && item.active)
    .map(item => ({
      key: item.key,
      competition: item.title || item.description || item.key,
      description: item.description || "",
      active: true
    }))
    .sort((a, b) => a.competition.localeCompare(b.competition));
  return { competitions, usage: result.usage };
}

function defaultKeys(competitions) {
  const keys = competitions.map(item => item.key);
  const preferred = DEFAULT_PRIORITY.filter(key => keys.includes(key));
  const remaining = keys.filter(key => !preferred.includes(key));
  return preferred.concat(remaining).slice(0, MAX_COMPETITIONS_PER_REFRESH);
}

async function getCompetitionOdds(key, env) {
  const path = "/sports/" + encodeURIComponent(key) +
    "/odds/?regions=" + encodeURIComponent(REGIONS) +
    "&markets=h2h&oddsFormat=decimal";
  const result = await oddsApi(path, env);
  const events = Array.isArray(result.payload) ? result.payload : [];
  return {
    key,
    competition: events[0]?.sport_title || key,
    events,
    usage: result.usage
  };
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    if (request.method !== "GET") return json({ success: false, error: "Only GET requests are supported." }, 405);

    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    try {
      if (path === "/" || path === "/api/health") {
        return json({ success: true, service: "15GAMES Intelligence API", status: "online", timestamp: new Date().toISOString() });
      }

      if (path === "/api/config") {
        return json({
          success: true,
          bookmakers: ["Bet365", "Pinnacle", "1xBet", "SportyBet", "Bet9ja", "Stake", "Hard Rock Bet"],
          regions: REGIONS,
          maxCompetitionsPerRefresh: MAX_COMPETITIONS_PER_REFRESH
        });
      }

      if (path === "/api/sports") {
        const result = await getSports(env);
        return json({
          success: true,
          totalSoccerCompetitions: result.competitions.length,
          competitions: result.competitions,
          requestUsage: result.usage,
          maxCompetitionsPerRefresh: MAX_COMPETITIONS_PER_REFRESH
        });
      }

      if (path === "/api/unified-odds" || path === "/api/multi-odds") {
        const sports = await getSports(env);
        const availableKeys = new Set(sports.competitions.map(item => item.key));
        const requested = url.searchParams.get("competitions");
        let selected = requested
          ? [...new Set(requested.split(",").map(value => value.trim()).filter(Boolean))]
          : defaultKeys(sports.competitions);

        if (!selected.length) return json({ success: false, error: "Select at least one competition." }, 400);
        if (selected.length > MAX_COMPETITIONS_PER_REFRESH) {
          return json({ success: false, error: "Select no more than " + MAX_COMPETITIONS_PER_REFRESH + " competitions per refresh." }, 400);
        }
        const invalid = selected.filter(key => !availableKeys.has(key));
        if (invalid.length) {
          return json({ success: false, error: "Some selected competitions are not currently active: " + invalid.join(", ") }, 400);
        }

        const results = [];
        const errors = [];
        const requestUsage = [];
        for (const key of selected) {
          try {
            const result = await getCompetitionOdds(key, env);
            const known = sports.competitions.find(item => item.key === key);
            results.push({
              key,
              competition: known?.competition || result.competition,
              events: result.events
            });
            requestUsage.push({ competition: key, ...result.usage });
          } catch (error) {
            errors.push({ competition: key, error: error.message, status: error.status || null });
            if (error.usage) requestUsage.push({ competition: key, ...error.usage });
          }
        }

        const fixtureCount = results.reduce((sum, item) => sum + item.events.length, 0);
        return json({
          success: results.length > 0,
          selectedCompetitions: selected,
          requestedCompetitionCount: selected.length,
          returnedCompetitionCount: results.length,
          fixtureCount,
          results,
          errors,
          requestUsage,
          regions: REGIONS,
          maxCompetitionsPerRefresh: MAX_COMPETITIONS_PER_REFRESH,
          timestamp: new Date().toISOString()
        }, results.length ? 200 : 502);
      }

      if (path === "/api/odds") {
        const sport = url.searchParams.get("sport");
        if (!sport || !sport.startsWith("soccer_")) {
          return json({ success: false, error: "Provide a soccer sport key using ?sport=." }, 400);
        }
        const available = await getSports(env);
        if (!available.competitions.some(item => item.key === sport)) {
          return json({ success: false, error: "That competition is not currently active." }, 404);
        }
        const result = await getCompetitionOdds(sport, env);
        return json({ success: true, ...result });
      }

      return json({ success: false, error: "Endpoint not found." }, 404);
    } catch (error) {
      return json({
        success: false,
        error: error.message || "Unexpected API error.",
        status: error.status || null,
        usage: error.usage || null
      }, error.status || 500);
    }
  }
};
