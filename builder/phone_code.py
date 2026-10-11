"""Date and account facts for the phone agent.

This file runs in two places:
  * inside the Freya workflow, as the source of a code step (generate.py embeds it with the spec), and
  * locally, in builder/test_phone_code.py, against the practice cases.

Rules for the Freya sandbox (kit/docs/tools-and-code.md): only json, re and datetime; never raise; no double
curly braces anywhere in this file; read and write workflow variables only through `vars`.
Nothing here may know a brief: every rule value (holidays, bands, deadlines, floors) comes from SPEC.
"""
import datetime
import json
import re

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
CALENDAR_DAYS = 70          # how far ahead the calendar text reaches


def day_text(d):
    return WEEKDAYS[d.weekday()] + " " + str(d.day) + " " + MONTHS[d.month - 1] + " " + str(d.year)


def money(x):
    try:
        return "%.2f" % float(x)
    except Exception:
        return str(x)


def parse_now(value):
    m = re.match(r"\s*(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ](\d{1,2}):(\d{2}))?", str(value or ""))
    if not m:
        return None
    return datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4) or 0), int(m.group(5) or 0))


def weekend_numbers(spec):
    names = [str(x).strip().lower()[:3] for x in (spec.get("weekend_days") or ["Saturday", "Sunday"])]
    return [i for i, w in enumerate(WEEKDAYS) if w.lower()[:3] in names]


def holiday_set(spec):
    out = set()
    for h in spec.get("holidays") or []:
        m = re.match(r"\s*(\d{4}-\d{2}-\d{2})", str(h))
        if m:
            out.add(m.group(1))
    return out


def is_business(d, spec):
    return d.weekday() not in weekend_numbers(spec) and d.isoformat() not in holiday_set(spec)


def next_business(d, spec, include_today=False):
    x = d if include_today else d + datetime.timedelta(days=1)
    for _ in range(400):
        if is_business(x, spec):
            return x
        x = x + datetime.timedelta(days=1)
    return x


def add_business_days(d, n, spec):
    x = d
    for _ in range(int(n)):
        x = next_business(x, spec)
    return x


def last_business_of_week(d, spec):
    """The last business day in the Monday-to-Sunday week that contains d, or None."""
    monday = d - datetime.timedelta(days=d.weekday())
    best = None
    for i in range(7):
        x = monday + datetime.timedelta(days=i)
        if is_business(x, spec):
            best = x
    return best


def band_for(days_late, spec):
    try:
        n = int(float(days_late))
    except Exception:
        return None
    for b in spec.get("bands") or []:
        try:
            if int(b.get("min_days_late")) <= n <= int(b.get("max_days_late")):
                return b
        except Exception:
            pass
    return None


def deadline_for(today, band, spec):
    if not band:
        return None
    count = int(band.get("deadline_count") or 0)
    if band.get("deadline_unit") == "calendar_days":
        return today + datetime.timedelta(days=count)
    return add_business_days(today, count, spec)


def allowed_dates(today, deadline, spec):
    """Every business day from today (if it is one) up to and including the deadline."""
    out, x = [], today
    if not deadline:
        return out
    for _ in range(400):
        if x > deadline:
            break
        if is_business(x, spec):
            out.append(x)
        x = x + datetime.timedelta(days=1)
    return out


def short_day(d):
    return d.isoformat() + " " + WEEKDAYS[d.weekday()][:3] + " " + str(d.day) + " " + MONTHS[d.month - 1][:3]


def parse_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for k in ("products", "items", "data"):
            if isinstance(value.get(k), list):
                return value[k]
        return None
    if isinstance(value, str) and value.strip()[:1] in ("[", "{"):
        s = value.strip()
        for attempt in (s, s.replace("'", '"').replace("True", "true").replace("False", "false").replace("None", "null")):
            try:
                return parse_list(json.loads(attempt))
            except Exception:
                pass
    return None


def read_products(v):
    """The product list of get_account, wherever the engine put it: a mapped variable, a JSON string, or
    flattened keys such as get_account_response.data.products.0.past_due."""
    for key in ["fx_products_raw", "products", "get_account_response.data.products", "load_account_response.data.products"]:
        got = parse_list(v.get(key))
        if got:
            return [p for p in got if isinstance(p, dict)]
    for key in list(v.keys()):
        if str(key).endswith("data.products"):
            got = parse_list(v.get(key))
            if got:
                return [p for p in got if isinstance(p, dict)]
    rows = {}
    for key in list(v.keys()):
        m = re.match(r"^(.*data\.products)\.(\d+)\.([A-Za-z_][A-Za-z0-9_]*)$", str(key))
        if m:
            rows.setdefault(int(m.group(2)), {})[m.group(3)] = v.get(key)
    return [rows[i] for i in sorted(rows)]


def product_info(p, index, today, spec):
    ptype = str(p.get("type") or "")
    conf = None
    for t in spec.get("product_types") or []:
        if str(t.get("type")) == ptype:
            conf = t
    label = ptype.replace("_", " ")
    floor = None
    if conf:
        template = str(conf.get("label_template") or label)
        label = re.sub(r"\[([A-Za-z_][A-Za-z0-9_]*)\]", lambda m: str(p.get(m.group(1), "")), template)
        floor = p.get(str(conf.get("floor_field") or ""))
    band = band_for(p.get("days_late"), spec)
    deadline = deadline_for(today, band, spec)
    return {
        "product_id": str(p.get("product_id") or ("p" + str(index + 1))),
        "label": label.strip(),
        "past_due": p.get("past_due"),
        "days_late": p.get("days_late"),
        "floor": floor,
        "band": band.get("name") if band else "unknown",
        "attempts": band.get("persuasion_attempts") if band else None,
        "offers": band.get("offers") if band else None,
        "deadline": deadline,
    }


def attempts_text(attempts):
    """Spell the offer limit out, so the agent does not reuse another product's count."""
    words = ["NO", "ONE", "TWO", "THREE", "FOUR", "FIVE"]
    try:
        n = int(attempts)
    except Exception:
        return str(attempts)
    word = words[n] if 0 <= n < len(words) else str(n)
    ordinals = ["first", "second", "third", "fourth", "fifth", "sixth"]
    nxt = ordinals[n] if 0 <= n < len(ordinals) else "further"
    return (str(n) + ". That means " + word + " offer" + ("" if n == 1 else "s") + " for this product, counted for this "
            + "product alone: once the customer has refused " + ("it" if n == 1 else "the last one") + ", make no " + nxt
            + " offer for this product (no lower amount, no other date); it ends without a promise and you go on to the next "
            + "product")


def offer_date(kind, today, deadline, spec):
    if kind == "end_of_week":
        d = last_business_of_week(today, spec)
        if d is None or d <= today:
            d = last_business_of_week(today + datetime.timedelta(days=7), spec)
        if d and deadline and d > deadline:
            d = deadline
        return d
    if kind == "deadline":
        return deadline
    if kind == "today":
        return today
    if kind == "next_business_day":
        return next_business(today, spec)
    return None


def offers_text(x, today, spec):
    """The product's persuasion offers as concrete amounts and dates, or "" when the spec has none."""
    offers = x.get("offers")
    if not isinstance(offers, list) or not offers:
        return ""
    parts = []
    for i, o in enumerate(offers):
        if not isinstance(o, dict):
            continue
        amount = {"full": money(x["past_due"]), "floor": money(x["floor"]),
                  "full_or_floor": money(x["past_due"]) + " (or the floor " + money(x["floor"])
                  + " if the customer already said the full amount is too much)"}.get(str(o.get("amount")))
        d = offer_date(str(o.get("date")), today, x["deadline"], spec)
        if amount and d:
            parts.append("offer " + str(i + 1) + ": " + amount + " on " + day_text(d) + " (" + d.isoformat() + ")")
        else:
            parts.append("offer " + str(i + 1) + ": " + str(o.get("text") or ""))
    if not parts:
        return ""
    return ("  Persuasion offers for this product, in this order, one after each refusal: " + "; ".join(parts)
            + ". Make exactly these offers for this product and no other (the question about paying everything today "
            + "is not one of them). When the customer has refused the last one, this product ends without a promise.")


def calendar_text(today, until, spec, deadlines=None):
    """One line per day. With the products' deadlines, a non-business day also names the first allowed date after
    it, and a day after a product's deadline says so, so the agent reads the answer instead of comparing dates."""
    lines, hol = [], holiday_set(spec)
    deadlines = [d for d in (deadlines or []) if d]
    monday = today - datetime.timedelta(days=today.weekday())
    x = today
    while x <= until:
        week = (x - monday).days // 7
        when = ["this week", "next week", "the week after next"][week] if week < 3 else str(week) + " weeks after this week"
        if x.isoformat() in hol:
            kind = "bank HOLIDAY, not a business day"
        elif x.weekday() in weekend_numbers(spec):
            kind = "weekend, not a business day"
        else:
            kind = "business day"
        if kind != "business day" and x > today:
            nb = next_business(x, spec)
            kind += "; first allowed date after it: " + day_text(nb) + " (" + nb.isoformat() + ")"
        late = [str(i + 1) for i, d in enumerate(deadlines) if x > d]
        if late:
            kind += "; AFTER the deadline of product " + ", ".join(late)
        lines.append("- " + x.isoformat() + " " + day_text(x) + " (" + when + ("; TODAY" if x == today else "") + "): " + kind)
        x = x + datetime.timedelta(days=1)
    return "\n".join(lines)


def hhmm(value):
    """'9:00', '09:00', '9.00' -> '09:00' (so times compare as text); '' when unreadable."""
    m = re.match(r"\s*(\d{1,2})[:.h](\d{2})", str(value or ""))
    return ("%02d:%s" % (int(m.group(1)), m.group(2))) if m else ""


def callback_text(now, spec):
    cb = spec.get("callback") or {}
    earliest, latest = hhmm(cb.get("earliest")), hhmm(cb.get("latest"))
    ahead = int(cb.get("max_business_days_ahead") or 0)
    today = now.date()
    days = [today] if is_business(today, spec) and not (latest and now.strftime("%H:%M") >= latest) else []
    x = today
    for _ in range(ahead):
        x = next_business(x, spec)
        days.append(x)
    parts = []
    for d in days:
        start = ("from " + earliest) if earliest else "any time"
        if d == today:
            current = now.strftime("%H:%M")
            start = ("from " + earliest) if earliest and earliest > current else ("later than now (" + current + ")")
        parts.append(day_text(d) + " (" + d.isoformat() + "), " + start + (" until " + latest if latest else ""))
    return "Allowed callback days and times: " + ("; ".join(parts) if parts else "none") + "."


def compute(v, spec):
    """Write the fx_* facts into v. Never raises."""
    try:
        now = parse_now(v.get("now")) or datetime.datetime.now()
        today = now.date()
        v["fx_today"] = today.isoformat()
        v["fx_today_text"] = day_text(today) + ", " + now.strftime("%H:%M")
        nb = next_business(today, spec)
        v["fx_next_business_day"] = day_text(nb) + " (" + nb.isoformat() + ")"
        facts = [
            "Today is " + day_text(today) + " (" + today.isoformat() + "), time " + now.strftime("%H:%M") + ".",
            "Today is " + ("" if is_business(today, spec) else "NOT ") + "a business day.",
            "Next business day after today: " + v["fx_next_business_day"] + ".",
        ]
        this_last = last_business_of_week(today, spec)
        next_last = last_business_of_week(today + datetime.timedelta(days=7), spec)
        if this_last:
            facts.append("Last business day of this week: " + day_text(this_last) + " (" + this_last.isoformat() + ").")
        if next_last:
            facts.append("Last business day of next week: " + day_text(next_last) + " (" + next_last.isoformat() + ").")
        v["fx_date_facts"] = "\n".join(facts)
        v["fx_callback_text"] = callback_text(now, spec)

        products = read_products(v)
        infos = [product_info(p, i, today, spec) for i, p in enumerate(products)]
        lines, until = [], today + datetime.timedelta(days=21)
        for n, x in enumerate(infos):
            dl = x["deadline"]
            if dl and dl > until:
                until = dl
            lines.append(
                "Product " + str(n + 1) + " (product_id " + x["product_id"] + "): " + x["label"] + ". Past due " + money(x["past_due"])
                + ". " + str(x["days_late"]) + " days late, " + str(x["band"]) + " band. Floor (lowest amount allowed): "
                + money(x["floor"]) + ". Latest allowed promise date (deadline): "
                + (day_text(dl) + " (" + dl.isoformat() + ")" if dl else "unknown") + ". Persuasion attempts for this product: " + attempts_text(x["attempts"]) + ".")
            offer_line = offers_text(x, today, spec)
            if offer_line:
                lines.append(offer_line)
            ok_days = allowed_dates(today, dl, spec)
            if ok_days:
                lines.append(
                    "  Allowed promise dates for product " + str(n + 1) + " (every business day from today to its deadline; "
                    + "a date in this list is allowed, any date not in it is not): " + ", ".join(short_day(d) for d in ok_days) + ".")
                gaps, g = [], today + datetime.timedelta(days=1)
                while g < dl:
                    if not is_business(g, spec):
                        gaps.append(short_day(g) + " -> " + short_day(next_business(g, spec)))
                    g = g + datetime.timedelta(days=1)
                if gaps:
                    lines.append("  Weekend days and holidays before the deadline of product " + str(n + 1)
                                 + ", each with the first allowed date after it: " + "; ".join(gaps)
                                 + ". A date after the deadline: the latest allowed date is the deadline.")
            v["fx_p" + str(n + 1) + "_deadline"] = dl.isoformat() if dl else ""
            v["fx_p" + str(n + 1) + "_floor"] = money(x["floor"])
        v["fx_product_count"] = str(len(infos))
        v["fx_account_facts"] = "\n".join(lines) if lines else "The account could not be read."
        v["fx_account_state"] = "ok" if lines else "missing"
        v["fx_calendar"] = calendar_text(today, until + datetime.timedelta(days=7), spec, [x["deadline"] for x in infos])
    except Exception as e:
        v["fx_error"] = str(e)[:300]
        for k in ("fx_today", "fx_today_text", "fx_next_business_day", "fx_date_facts", "fx_callback_text",
                  "fx_account_facts", "fx_calendar", "fx_product_count", "fx_account_state"):
            if k not in v:
                v[k] = ""
    return v
