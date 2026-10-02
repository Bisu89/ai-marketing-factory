"""Shared, series-wide prompt pieces for Biblical Figures (character bibles + style blocks).

Add a new recurring character here once, then reference it by key from any episode spec.
"""

CHAR = {
    "J": (
        "recurring character Judas Iscariot: Judean man in his early 30s, lean wiry build, olive-tan "
        "weathered skin, short dark curly hair, short close-trimmed black beard, deep-set dark brown eyes "
        "under heavy brows, a faint vertical worry line between the brows, intense guarded expression, "
        "undyed oatmeal-colored linen tunic, faded dark red wool mantle over one shoulder, a worn leather "
        "money pouch on a cord at his belt, leather sandals, no jewelry; keep his face, hair, beard and "
        "clothing identical whenever he appears"
    ),
    "JC": (
        "recurring character Jesus of Nazareth: Galilean man in his early 30s, calm serious face with gentle "
        "dark brown eyes, olive skin, long wavy dark brown hair parted in the middle falling to the shoulders, "
        "short full dark beard, plain off-white linen tunic, simple brown wool mantle, leather sandals, dignified "
        "and quiet presence, no halo, no glow; keep his face, hair, beard and clothing identical whenever he appears"
    ),
    "C": (
        "recurring character Caiaphas the high priest: Judean man in his late 50s, heavy-set, long graying "
        "beard, stern calculating eyes, fine white linen robe under a deep indigo-blue outer robe, simple "
        "white linen head covering, woven sash belt, no jewelry; keep his face, beard and clothing identical "
        "whenever he appears"
    ),
    "P": (
        "recurring character Pontius Pilate: Roman man in his mid-40s, clean-shaven, short cropped dark hair "
        "going gray at the temples, hard narrow face, thin lips, cold appraising eyes, white wool tunic with "
        "a narrow purple stripe under a heavy off-white wool cloak pinned at the shoulder, no jewelry except "
        "a plain iron signet ring; keep his face, hair and clothing identical whenever he appears"
    ),
    "MM": (
        "recurring character Mary Magdalene: Galilean woman in her late 20s, dignified composed face, warm "
        "olive skin, dark wavy hair mostly covered by a deep blue-grey linen head veil with a few loose "
        "strands at the temple, steady thoughtful dark eyes, plain undyed linen tunic under a deep blue-grey "
        "mantle, no jewelry, modest and resolute bearing; keep her face, hair and clothing identical whenever "
        "she appears"
    ),
    "PT": (
        "recurring character Simon Peter: Galilean fisherman in his late 30s, stocky sturdy build, weathered "
        "sun-browned face, short curly grey-flecked dark hair and a full grey-flecked beard, deep-set warm "
        "brown eyes with a earnest impulsive expression, plain undyed wool fisherman's tunic, rope belt, "
        "rough brown outer cloak, no jewelry; keep his face, hair, beard and clothing identical whenever he "
        "appears"
    ),
    "PL": (
        "recurring character Paul of Tarsus: Jewish-Roman man in his 40s, short average build, receding "
        "dark hairline, short dark beard flecked with grey, intense penetrating eyes, prominent brow, plain "
        "undyed linen tunic under a dark travel-worn wool cloak, leather satchel, no jewelry; keep his face, "
        "hair, beard and clothing identical whenever he appears"
    ),
    "HA": (
        "recurring character Herod Antipas: Judean-Idumean ruler in his late 40s, fleshy face, trimmed graying "
        "beard, heavy-lidded mocking eyes, rich purple and gold embroidered robe, gold circlet on oiled dark "
        "hair, rings on his fingers; keep his face, beard and clothing identical whenever he appears"
    ),
    "HD": (
        "recurring character Herodias: Judean-Idumean noblewoman in her 30s, striking composed features, "
        "elaborate dark hair pinned up with gold ornaments, deep red and gold embroidered gown, cold "
        "calculating expression, a thin gold circlet, no other jewelry; keep her face, hair and clothing "
        "identical whenever she appears"
    ),
    "JB": (
        "recurring character John the Baptist: Judean man in his early 30s, gaunt ascetic build, deeply "
        "sun-weathered skin, wild unkempt dark hair and a thick untrimmed beard, intense piercing eyes, rough "
        "undyed camel-hair tunic cinched with a wide leather belt, bare feet, no jewelry; keep his face, hair, "
        "beard and clothing identical whenever he appears"
    ),
    "AN": (
        "recurring character Annas the former high priest: elderly Judean man in his 70s, thin frame, long "
        "white beard, deeply lined face, hooded shrewd eyes, white linen robe under a deep crimson outer "
        "robe, white linen head covering, a thin gold chain; keep his face, beard and clothing identical "
        "whenever he appears"
    ),
}

# Which pool images a character key marks as "only reusable when this person is in the story".
CHAR_NAMES = {"J": "judas", "JC": "jesus", "C": "caiaphas", "P": "pilate", "MM": "magdalene",
             "PT": "peter", "PL": "paul", "HA": "herod", "HD": "herodias", "JB": "baptist", "AN": "annas"}

# Style history: Ep1 used a photoreal "cinematic" look; from Ep2 the series is an aged old-master
# painting look (user: the old-painting style suits Bible stories and earned the channel's views).
# Pool images only reuse within the same STYLE_NAME (see bf.py validate).
# 2026-09-28: hand-generating 60-80 images per episode was too much work. From Ep2 the series is
# generated by the app's own image API (gpt-image-1-mini, quality low, ~$0.006/image) with the exact
# prompt shape of the old project-91 video that earned views -- that model/quality is what gives the
# soft, faded, old-painting look. ~25-30 images per long video, each used up to 3 times.
STYLE_NAME = "mini_low"
STYLE_MARKERS = {"cinematic": "Cinematic historical", "painting": "Aged oil painting",
                 "mini_low": "Simple, consistent illustration style"}

AI_TONE = ("authoritative, measured and cinematic, like a history-documentary narrator -- respectful and "
           "neutral on matters of faith")
AI_STYLE = "narrative biography of one figure from the Gospels or early-church period"
AI_STYLE_PROMPT = (  # project 91's image_style_prompt, minus its per-character bible
    "cinematic historical documentary still, painterly photorealistic illustration, first-century Roman "
    "Judea setting, period-accurate clothing architecture and landscape, dramatic natural light, volumetric "
    "atmosphere, muted earthy desaturated color grade, fine film grain, epic but grounded scale, reverent and "
    "tasteful, no blood, no gore, no wounds, no corpses, no modern objects, no lettering, no on-screen text, "
    "no watermark"
)
AI_ORIENTATION = {"long": "horizontal 16:9 composition", "short": "vertical 9:16 composition",
                  "thumb": "horizontal 16:9 composition"}

_PAINTING = (
    "Aged oil painting in the style of 17th-century Baroque old-master religious art (Caravaggio, Rembrandt), "
    "rich visible brushstrokes, fine craquelure and slightly worn varnish texture, warm sepia, umber and ochre "
    "palette with deep brown shadows, dramatic candlelit chiaroscuro, soft painterly edges, period-accurate "
    "first-century Judean and Roman clothing and architecture, museum masterpiece quality."
)
_RESTRICTIONS = (
    " IMPORTANT STYLE RESTRICTIONS: a painting, not a photograph, not photorealistic, not a 3D render, not "
    "modern digital art, not anime, no halos, no glowing divine light rays, no modern objects, no blood, no "
    "gore, no wounds, no corpses, no text, no letters, no signature, no captions, no watermark, no picture "
    "frame, no border."
)

LONG_STYLE = (
    _PAINTING + " Wide landscape composition framed for a 16:9 crop: keep the main subject in the central "
    "horizontal band, nothing important near the top or bottom edges." + _RESTRICTIONS
)

SHORT_STYLE = (
    _PAINTING + " Close, intimate framing with one clear focal subject and a strong readable silhouette on a "
    "phone screen. Tall vertical composition framed for a 9:16 crop: subject centered in the middle vertical "
    "band, nothing important near the left or right edges, keep the lower quarter of the frame calm and "
    "uncluttered." + _RESTRICTIONS
)

# YouTube thumbnail: a long video's views depend on it, so it gets its own purpose-built image.
THUMB_STYLE = (
    _PAINTING + " YouTube thumbnail composition: one face very large and close, filling the right half of the "
    "frame, eyes looking straight at the viewer, strong contrast and a bright warm rim light so it reads at "
    "tiny size, dark simple background, the left third of the frame dark and empty for large title text "
    "added later." + _RESTRICTIONS
)

LEAD = {"long": "Create a landscape image.", "short": "Create a tall portrait image.", "thumb": "Create a landscape image."}
STYLE = {"long": LONG_STYLE, "short": SHORT_STYLE, "thumb": THUMB_STYLE}

# Pool images that must not be reused (or only with care), with the reason. Keyed by filename.
POOL_FLAGS = {
    "017_judas_alone_road_outsider.png": "avoid: background figure looks like Jesus with face visible",
    "060_rope_bare_tree_dusk.png": "never as thumbnail (suicide imagery)",
}


def build_prompt(version: str, scene: str, chars: list[str], extra_chars: dict | None = None) -> str:
    bibles = {**CHAR, **(extra_chars or {})}
    if STYLE_NAME == "mini_low":  # same shape as the app's imagegen_generate._image_prompt
        text = scene + ("; " + "; ".join(bibles[c] for c in chars) if chars else "")
        suffix = (f"Simple, consistent illustration style matching the rest of this video's visuals, evoking a "
                  f"{AI_TONE} tone in a {AI_STYLE} style, {AI_ORIENTATION[version]}, no text or watermarks in "
                  f"the image.")
        return f"{text}. {suffix} {AI_STYLE_PROMPT}"
    text = f"{LEAD[version]} {scene}"
    if chars:
        text += "; " + "; ".join(bibles[c] for c in chars)
    return text + ". " + STYLE[version]
