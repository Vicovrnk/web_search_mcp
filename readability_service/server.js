/**
 * HTTP service: POST /extract { html, pageUrl } -> Readability article JSON.
 */

import http from "node:http";
import { Readability } from "@mozilla/readability";
import { JSDOM } from "jsdom";
import createDOMPurify from "dompurify";

const PORT = Number(process.env.PORT ?? "3010");
const MAX_BODY_BYTES = Math.max(
  4096,
  Number(process.env.MAX_BODY_BYTES ?? "1000000"),
);

function jsonResponse(res, status, body) {
  const payload = JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(payload, "utf8"),
  });
  res.end(payload);
}

function sanitizeHtml(window, html) {
  const purify = createDOMPurify(window);
  return purify.sanitize(html, { WHOLE_DOCUMENT: false });
}

async function readBody(req, limit) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > limit) {
      return { error: "payload_too_large", size: total };
    }
    chunks.push(chunk);
  }
  const raw = Buffer.concat(chunks).toString("utf8");
  try {
    return { json: JSON.parse(raw) };
  } catch {
    return { error: "invalid_json" };
  }
}

function handleExtract(req, res, body) {
  if (typeof body.html !== "string" || typeof body.pageUrl !== "string") {
    jsonResponse(res, 400, {
      ok: false,
      error: "Expected JSON body with string fields `html` and `pageUrl`.",
    });
    return;
  }
  if (!body.html.trim()) {
    jsonResponse(res, 400, {
      ok: false,
      error: "`html` must not be empty.",
    });
    return;
  }

  let dom;
  try {
    dom = new JSDOM(body.html, { url: body.pageUrl.trim() });
  } catch (err) {
    jsonResponse(res, 400, {
      ok: false,
      error: `Failed to parse HTML: ${err?.message ?? err}`,
    });
    return;
  }

  const article = new Readability(dom.window.document).parse();

  if (!article) {
    jsonResponse(res, 200, {
      ok: false,
      error: "Readability could not extract an article from this page.",
    });
    return;
  }

  const contentSanitized = sanitizeHtml(dom.window, article.content ?? "");

  jsonResponse(res, 200, {
    ok: true,
    article: {
      title: article.title ?? null,
      content: contentSanitized,
      textContent: article.textContent ?? null,
      excerpt: article.excerpt ?? null,
      byline: article.byline ?? null,
      siteName: article.siteName ?? null,
      publishedTime: article.publishedTime ?? null,
      lang: article.lang ?? null,
    },
  });
}

const server = http.createServer(async (req, res) => {
  if (req.method === "GET" && req.url === "/healthz") {
    res.writeHead(200, { "Content-Type": "text/plain" });
    res.end("ok");
    return;
  }

  if (req.method !== "POST" || req.url !== "/extract") {
    jsonResponse(res, 404, { ok: false, error: "Not found." });
    return;
  }

  const parsed = await readBody(req, MAX_BODY_BYTES);
  if (parsed.error === "payload_too_large") {
    jsonResponse(res, 413, {
      ok: false,
      error: `Request body exceeds limit of ${MAX_BODY_BYTES} bytes.`,
    });
    return;
  }
  if (parsed.error === "invalid_json") {
    jsonResponse(res, 400, { ok: false, error: "Invalid JSON body." });
    return;
  }

  try {
    handleExtract(req, res, parsed.json);
  } catch (err) {
    jsonResponse(res, 500, {
      ok: false,
      error: err?.message ?? String(err),
    });
  }
});

server.listen(PORT, "0.0.0.0", () => {
  // eslint-disable-next-line no-console
  console.log(`readability-service listening on ${PORT}`);
});
