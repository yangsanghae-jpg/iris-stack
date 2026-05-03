import "dotenv/config";
import express from "express";
import Firecrawl from "@mendable/firecrawl-js";

const app = express();
app.use(express.json({ limit: "1mb" }));

const PORT = Number(process.env.PORT || 8020);
const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY || "";

let firecrawl = null;
if (FIRECRAWL_API_KEY) {
  firecrawl = new Firecrawl({ apiKey: FIRECRAWL_API_KEY });
} else {
  console.warn("[L4-search] FIRECRAWL_API_KEY is not set");
}

app.get("/health", (req, res) => {
  res.json({
    ok: true,
    app: "iris-l4-search",
    provider: "firecrawl",
  });
});

app.post("/search", async (req, res) => {
  const query = String(req.body?.query ?? "").trim();
  const limit = Math.min(Math.max(Number(req.body?.limit ?? 3) || 3, 1), 10);

  if (!query) {
    return res.status(400).json({
      ok: false,
      error: "query is required",
    });
  }

  if (!firecrawl) {
    return res.status(503).json({
      ok: false,
      error: "FIRECRAWL_API_KEY is not configured",
    });
  }

  try {
    console.log("[L4-search] search request:", { query, limit });
    const result = await firecrawl.search(query, { limit });

    const raw = Array.isArray(result?.data)
      ? result.data
      : Array.isArray(result?.web)
        ? result.web
        : [];

    const results = raw.slice(0, limit).map((item) => ({
      title: item?.title || item?.metadata?.title || "",
      url: item?.url || item?.metadata?.sourceURL || "",
      snippet:
        item?.description ||
        item?.snippet ||
        item?.markdown ||
        item?.content ||
        "",
    }));

    return res.json({
      ok: true,
      query,
      count: results.length,
      results,
    });
  } catch (err) {
    console.error("[L4-search] search error:", err?.message || err);
    return res.status(500).json({
      ok: false,
      error: String(err?.message || err),
    });
  }
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`[L4-search] listening on ${PORT}`);
});
