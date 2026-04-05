"""
Standalone-Test für Value+Growth Parsing (kein Netzwerk, kein cloudscraper-Import).
"""
import re
from bs4 import BeautifulSoup


def parse_value_and_growth(right_td):
    if not right_td:
        return "", ""

    value_price = ""
    growth_pct  = ""

    # 0. PRIMÄR: div.ctlsets-value
    value_div = right_td.find("div", class_="ctlsets-value")
    if value_div:
        cursor_span = value_div.find("span", class_="cursor-help")
        if cursor_span:
            price_text = cursor_span.get_text(strip=True)
            if re.search(r"[€$£¥]\s*[\d,]+\.?\d*", price_text):
                value_price = price_text
        if not value_price:
            pm = re.search(r"[€$£¥]\s*[\d,]+\.?\d*", value_div.get_text())
            if pm:
                value_price = pm.group(0).strip()

    # 1. span.cursor-help nach "value"-Node
    if not value_price:
        children = list(right_td.descendants)
        for i, node in enumerate(children):
            node_text = node.get_text(strip=True) if hasattr(node, "get_text") else str(node).strip()
            if node_text.lower() == "value":
                for j in range(i + 1, min(i + 15, len(children))):
                    candidate = children[j]
                    if hasattr(candidate, "get") and "cursor-help" in (candidate.get("class") or []):
                        price_text = candidate.get_text(strip=True)
                        if re.search(r"[€$£¥]\s*[\d,]+\.?\d*", price_text):
                            value_price = price_text
                            break
                if value_price:
                    break

    # 2. Regex "Value ... €XX"
    if not value_price:
        plain = right_td.get_text(separator="|", strip=True)
        m = re.search(r"Value[^€$£¥\d]{0,30}([€$£¥]\s*[\d,]+\.?\d*)", plain, re.I)
        if m:
            value_price = m.group(1).strip()

    # 3. Zweiter Preis = Value
    if not value_price:
        plain = right_td.get_text(separator="|", strip=True)
        all_prices = re.findall(r"[€$£¥]\s*[\d,]+\.?\d*", plain)
        if len(all_prices) >= 2:
            value_price = all_prices[1]

    # 4. Fallback: Retail aus <b>
    if not value_price:
        bold = right_td.find("b")
        if bold:
            value_price = bold.get_text(strip=True)
        if not value_price:
            pm = re.search(r"[€$£¥]\s*[\d,]+\.?\d*", right_td.get_text())
            if pm:
                value_price = pm.group(0).strip()

    # 5a. Growth: icon-up/down
    growth_icon = right_td.find("i", class_=re.compile(r"icon-(up|down)"))
    if growth_icon:
        for sibling in growth_icon.next_siblings:
            sib_text = sibling.get_text(strip=True) if hasattr(sibling, "get_text") else str(sibling).strip()
            m = re.search(r"([+\-]\s*[\d,.]+\s*%)", sib_text)
            if m:
                growth_pct = m.group(1).strip().replace(" ", "")
                break
        if not growth_pct:
            parent = growth_icon.parent
            if parent:
                parent_text = parent.get_text(separator=" ", strip=True)
                m = re.search(r"([+\-]\s*[\d,.]+\s*%)", parent_text)
                if m:
                    growth_pct = m.group(1).strip().replace(" ", "")

    # 5b. Growth: Descendants nach "growth"
    if not growth_pct:
        children = list(right_td.descendants)
        for i, node in enumerate(children):
            node_text = node.get_text(strip=True) if hasattr(node, "get_text") else str(node).strip()
            if node_text.lower() == "growth":
                for j in range(i + 1, min(i + 20, len(children))):
                    candidate = children[j]
                    cand_text = candidate.get_text(strip=True) if hasattr(candidate, "get_text") else str(candidate).strip()
                    m = re.search(r"([+\-]\s*[\d,.]+\s*%)", cand_text)
                    if m:
                        growth_pct = m.group(1).strip().replace(" ", "")
                        break
                if growth_pct:
                    break

    # 6. Regex Growth
    if not growth_pct:
        plain = right_td.get_text(separator="|", strip=True)
        m = re.search(r"Growth[^+\-\d]{0,30}([+\-]\s*[\d,.]+\s*%)", plain, re.I)
        if m:
            growth_pct = m.group(1).strip().replace(" ", "")

    return value_price, growth_pct


# ─── Tests ────────────────────────────────────────────────────────────────────

tests = [
    {
        "name": "Retired Set mit Value + Growth (bestätigte Struktur)",
        "html": '''<td class="ctlsets-right">
  <b>€24.99</b>
  <div class="ctlsets-retail">Retail <span class="cursor-help">€24.99</span></div>
  <div class="ctlsets-value">Value <span class="cursor-help">€147.88</span></div>
  <div>Growth <i class="icon-up-green-10"></i> +491.8%</div>
</td>''',
        "expect_value": "€147.88",
        "expect_growth": "+491.8%",
    },
    {
        "name": "Retired Set mit hohem Growth (Bionicle-Beispiel)",
        "html": '''<td class="ctlsets-right">
  <b>€9.99</b>
  <div class="ctlsets-value">Value <span class="cursor-help">€183.83</span></div>
  <div>Growth <i class="icon-up-green-10"></i> +819.6%</div>
</td>''',
        "expect_value": "€183.83",
        "expect_growth": "+819.6%",
    },
    {
        "name": "Aktives Set ohne Value (Fallback auf Retail)",
        "html": '''<td class="ctlsets-right">
  <b>€199.99</b>
</td>''',
        "expect_value": "€199.99",
        "expect_growth": "",
    },
    {
        "name": "Negativer Growth (rot)",
        "html": '''<td class="ctlsets-right">
  <b>€99.99</b>
  <div class="ctlsets-value">Value <span class="cursor-help">€85.00</span></div>
  <div>Growth <i class="icon-down-red-10"></i> -15.0%</div>
</td>''',
        "expect_value": "€85.00",
        "expect_growth": "-15.0%",
    },
]

all_ok = True
for t in tests:
    soup = BeautifulSoup(t["html"], "lxml")
    td = soup.find("td", class_="ctlsets-right")
    val, grw = parse_value_and_growth(td)
    ok_v = val == t["expect_value"]
    ok_g = grw == t["expect_growth"]
    status = "✅" if (ok_v and ok_g) else "❌"
    print(f"{status} {t['name']}")
    if not ok_v:
        print(f"   Value:  erwartet {repr(t['expect_value'])}, bekommen {repr(val)}")
    if not ok_g:
        print(f"   Growth: erwartet {repr(t['expect_growth'])}, bekommen {repr(grw)}")
    if ok_v and ok_g:
        print(f"   Value={repr(val)}, Growth={repr(grw)}")
    all_ok = all_ok and ok_v and ok_g

print()
print("✅ Alle Tests bestanden!" if all_ok else "❌ Es gibt fehlgeschlagene Tests!")
