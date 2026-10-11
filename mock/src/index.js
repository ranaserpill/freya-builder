// Mock of the bank's statement services for the final case, on Cloudflare Workers.
// Answers come verbatim from the case's test-environment/test-customers.json (copied to ./customers.json at deploy):
// same HTTP status, same body, same delay. The path -> service mapping follows the integration document; paths are
// matched loosely ("/cards/list", "/cards.list", "/api/v1/cards/list" all mean cards.list) until the document fixes them.
import data from "./customers.json";

const SERVICES = ["cards.list", "cards.balance", "statement.week.get", "statement.week.decide",
                  "statement.week.change", "contact.email.get", "statement.pdf.send"];
const BY_NO = Object.fromEntries((data.customers || []).map(c => [String(c.customerNo), c]));

function serviceFor(path) {
  const flat = path.toLowerCase().replace(/[^a-z]+/g, ".").replace(/^\.|\.$/g, "");
  return SERVICES.find(s => flat === s || flat.endsWith("." + s)) || null;
}

// Find a value in the body (or query) whose key looks like one of the hints, at any depth.
function pick(obj, hints) {
  if (!obj || typeof obj !== "object") return undefined;
  for (const [k, v] of Object.entries(obj)) {
    const key = k.toLowerCase();
    if (hints.some(h => key.includes(h)) && (typeof v === "string" || typeof v === "number")) return String(v);
  }
  for (const v of Object.values(obj)) {
    const found = pick(v, hints);
    if (found !== undefined) return found;
  }
  return undefined;
}

// Contract: the card number is sent exactly as cards.list returned it. We also accept a full 16-digit number that fits
// the mask (production may send full numbers); anything shorter only when exactly one card fits.
function matchCard(keys, given) {
  if (!given) return undefined;
  const g = String(given).trim();
  if (keys.includes(g)) return g;
  const digits = g.replace(/\D/g, "");
  if (digits.length === 16) {
    return keys.find(k => k.length === 16 && [...k].every((ch, i) => ch === "*" || ch === digits[i]));
  }
  const fits = keys.filter(k => digits.length >= 4 && k.endsWith(digits.slice(-4)) && (g.includes("*") ? k.slice(0, 6) === g.slice(0, 6) : true));
  return fits.length === 1 ? fits[0] : undefined;
}

const json = (status, body) => new Response(JSON.stringify(body), {status, headers: {"content-type": "application/json; charset=utf-8"}});

// Contract section 4: error answers have no `data`, only `result`.
function errorBody(code, message, type, rootCause) {
  const guid = crypto.randomUUID().replace(/-/g, "");
  return {result: {guid, returnCode: code, messageText: message, code, message, type,
                   details: {guid, rootCause, errorOrigin: "ivr-gateway-test:ivr-channel-v0"}}};
}
// No entry for the customer/card/week: the service's 404 from the contract, else 400 INVALID_ARGUMENTS_ERROR.
const NOT_FOUND = {
  "cards.list": ["FB_IVR_CHANNEL_102", "Müşteriye ait geçerli kart bilgisi bulunamadı."],
  "cards.balance": ["FB_IVR_CHANNEL_120", "Kart bakiye servisi hatası: kart bulunamadı"],
  "statement.week.get": ["FB_IVR_CHANNEL_121", "Hesap kesim servisi hatası: kart bulunamadı"],
  "statement.pdf.send": ["FB_IVR_CHANNEL_107", "Pdf dokümanı bulunamadı"],
};
function notFound(service) {
  const nf = NOT_FOUND[service];
  if (nf) return json(404, errorBody(nf[0], nf[1], "WARNING", "NotFoundException"));
  return json(400, errorBody("INVALID_ARGUMENTS_ERROR", "invalid arguments", "ERROR", "ValidationException"));
}
function missing(field) {
  return json(400, errorBody("INVALID_ARGUMENTS_ERROR", `${field} cannot be empty`, "ERROR", "ValidationException"));
}
// Required request fields per service (contract section 5); a missing/empty one is a 400 naming the field.
const REQUIRED = {
  "cards.list": [["customerNo", ["customerno", "customernumber"]]],
  "cards.balance": [["card number", ["cardnumber"]]],
  "statement.week.get": [["card number", ["cardnumber"]]],
  "statement.week.decide": [["card number", ["cardnumber"]], ["newStatementWeek", ["newstatementweek"]]],
  "statement.week.change": [["card number", ["cardnumber"]], ["newStatementWeek", ["newstatementweek"]]],
  "contact.email.get": [["customerNo", ["customerno", "customernumber"]], ["intAddressInfoType", ["intaddressinfotype"]]],
  "statement.pdf.send": [["customerNo", ["customerno", "customernumber"]], ["card number", ["cardnumber"]]],
};

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/" || url.pathname === "/health") return json(200, {ok: true, services: SERVICES, customers: Object.keys(BY_NO).length});
    const service = serviceFor(url.pathname);
    if (!service) return json(404, errorBody("NOT_FOUND", "unknown service path", "ERROR", "NotFoundException"));
    let body = {};
    try { body = request.method === "GET" ? {} : await request.json(); } catch { body = {}; }
    const input = {...Object.fromEntries(url.searchParams), ...body};
    for (const [label, hints] of REQUIRED[service]) {
      const v = pick(input, hints);
      if (v === undefined || String(v).trim() === "") return missing(label);
    }
    const isLeaf = e => e && typeof e === "object" && ("http" in e || "response" in e || "yanit" in e);
    const customerNo = String(pick(input, ["customerno", "customernumber"]) || "").replace(/\D/g, "");
    const cardGiven = pick(input, ["cardnumber"]);
    // Card services are looked up by card number alone (contract: called with the card number).
    let entry;
    if (["cards.balance", "statement.week.get", "statement.week.decide", "statement.week.change"].includes(service)) {
      const owners = customerNo && BY_NO[customerNo] ? [BY_NO[customerNo]] : Object.values(BY_NO);
      for (const c of owners) {
        const byCard = c.services[service];
        if (!byCard) continue;
        const card = matchCard(Object.keys(byCard), cardGiven);
        if (card) { entry = byCard[card]; break; }
      }
      if (entry && !isLeaf(entry)) {                                             // keyed by requested week
        entry = entry[String(pick(input, ["newstatementweek"]) || "").replace(/\D/g, "")];
      }
    } else {
      const customer = BY_NO[customerNo];
      entry = customer ? customer.services[service] : undefined;
      if (entry && !isLeaf(entry)) {                                             // defensive: keyed by card
        const card = matchCard(Object.keys(entry), cardGiven);
        entry = card ? entry[card] : undefined;
      }
    }
    if (!isLeaf(entry)) return notFound(service);
    const delay = Number(entry.gecikmeSaniye || entry.delaySeconds || 0);
    if (delay > 0) await new Promise(r => setTimeout(r, delay * 1000));
    return json(Number(entry.http || 200), entry.response ?? entry.yanit ?? {});
  },
};
