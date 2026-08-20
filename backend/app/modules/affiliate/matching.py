"""Story -> Product Category matching. Two distinct steps, kept apart on
purpose:

1. Category recommendation (prompt built here, pure) genuinely needs
   semantic/creative inference -- this task's own example ("Female
   self-worth" -> self-care, beauty, perfume, home decor, gifts) has no
   direct keyword overlap a plain tag-matching function could ever find
   -- so it's an AI call. The actual call_structured() invocation happens
   in the composition root (app/api/v1/endpoints/affiliate_recommend.py);
   this module must never import app.modules.ai (per
   app/modules/README.md, a module may never import another module).

2. Product matching (match_products, fully deterministic) is the opposite
   choice on purpose, mirroring Task 08/09's own "no ML, transparent,
   hand-tunable weighting" convention: given the AI-recommended categories
   (already carrying their own relevance/reason), rank ACTIVE products by
   combining scoring.py's static, intrinsic product_score with the
   category's own contextual relevance --
       final_score = category_relevance x product_score
   -- the same "static score x contextual factor" shape Task 09's
   recommendation_service.py already established. A product whose
   category/tags don't overlap ANY recommended category is never
   returned -- there is no such thing as a 0-relevance "recommendation"
   here (see this task's own "do NOT inject products into every story").
"""

from dataclasses import dataclass, field

from app.modules.affiliate.models import AffiliateProduct

CATEGORY_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "categories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "relevance": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["category", "relevance", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["categories"],
        "additionalProperties": False,
    },
}

_CATEGORY_SYSTEM_PROMPT = (
    "Ban la chuyen gia affiliate marketing. Cho mot mo ta noi dung/cau chuyen (audience, chu de, cam xuc), "
    "hay de xuat cac PRODUCT CATEGORY (danh muc san pham) that su lien quan de gioi thieu affiliate cho khan gia nay. "
    "Chi de xuat category thuc su phu hop voi audience va cam xuc cua noi dung -- khong de xuat category chung chung "
    "khong lien quan. Moi category can mot ly do ro rang, cu the, giai thich vi sao no phu hop voi audience/cau chuyen nay.\n\n"
    "QUAN TRONG ve dinh dang category: moi category PHAI la mot NHAN NGAN, GON (1-3 tu, giong ten danh muc "
    "thuong mai dien tu that -- vi du 'self-care', 'beauty', 'perfume', 'home decor', 'gifts', 'skincare', "
    "'journals') -- KHONG viet thanh cau mo ta dai. Nhan nay se duoc dung de khop truc tiep voi truong "
    "category cua san pham trong catalog, nen phai la mot tu/cum tu co the lam ten danh muc thuc su, "
    "khong phai mot cau giai thich."
)


def build_category_prompt(story_text: str, max_categories: int = 6) -> tuple[str, str]:
    if not story_text.strip():
        raise ValueError("story_text khong duoc de trong.")
    user_message = (
        f"Noi dung/cau chuyen: {story_text.strip()}\n\n"
        f"De xuat toi da {max_categories} product category (nhan ngan, 1-3 tu -- xem huong dan dinh dang), "
        "moi category kem relevance (0-1) va reason (1 cau, giai thich vi sao phu hop voi audience/cam xuc "
        "cua noi dung nay).\n\n"
        'Vi du dinh dang mong muon cho "Female self-worth": self-care, beauty, perfume, home decor, gifts.'
    )
    return _CATEGORY_SYSTEM_PROMPT, user_message


def parse_category_response(raw: str) -> list[dict]:
    import json

    data = json.loads(raw)
    categories = data.get("categories", [])
    result = []
    for c in categories:
        relevance = max(0.0, min(1.0, float(c["relevance"])))
        result.append({"category": str(c["category"]).strip(), "relevance": relevance, "reason": str(c["reason"]).strip()})
    result.sort(key=lambda c: c["relevance"], reverse=True)
    return result


@dataclass
class ProductMatch:
    product: AffiliateProduct
    category_relevance: float
    category_reason: str
    final_score: float | None
    reasons: list[str] = field(default_factory=list)


def _find_match(value: str, categories: list[dict]) -> dict | None:
    """Case-insensitive exact match first, then substring containment
    either direction (e.g. AI category "beauty" vs. catalog category
    "Beauty Products") -- still fully deterministic, just tolerant of
    natural wording/pluralization differences between an AI-generated
    label and a human-entered catalog category.
    """
    key = value.strip().lower()
    if not key:
        return None
    for c in categories:
        ck = c["category"].strip().lower()
        if ck == key or ck in key or key in ck:
            return c
    return None


def match_products(products: list[AffiliateProduct], categories: list[dict], limit: int = 10) -> list[ProductMatch]:
    matches: list[ProductMatch] = []
    for p in products:
        if not p.active:
            continue

        cat = _find_match(p.category, categories)
        matched_via_tag = False
        if cat is None and p.tags:
            for tag in p.tags:
                cat = _find_match(str(tag), categories)
                if cat is not None:
                    matched_via_tag = True
                    break

        if cat is None:
            continue  # no overlap at all -- never recommended, see module docstring

        relevance = cat["relevance"] * 0.7 if matched_via_tag else cat["relevance"]
        reasons = [
            f"{'Khớp qua tag' if matched_via_tag else 'Khớp category'} '{cat['category']}' "
            f"(relevance {relevance:.2f}): {cat['reason']}"
        ]

        if p.product_score is not None:
            final_score = round(relevance * p.product_score, 2)
            reasons.append(f"Product Score nội tại: {p.product_score:.1f}/100.")
        else:
            final_score = round(relevance * 50, 2)
            reasons.append("Chưa tính Product Score cho sản phẩm này -- dùng điểm trung tính 50/100 tạm thời.")

        matches.append(
            ProductMatch(product=p, category_relevance=relevance, category_reason=cat["reason"], final_score=final_score, reasons=reasons)
        )

    matches.sort(key=lambda m: m.final_score or 0, reverse=True)
    return matches[:limit]
