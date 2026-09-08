"""
"Noaniqlik xavfsizligi" qoidasining umumiy amalga oshirilishi: matnni
mahsulotga moslashtirishda, aniq ishonch bo'lmasa, hech qachon avtomatik
"eng yaqin" javobni tanlab olmaslik kerak.

`best_name_match` — tarmoqsiz, kutubxonasiz (faqat stdlib `difflib`) ishlaydigan
YENGIL standart moslashtiruvchi. Bu Analytics'ning kuchli AI-parser'i
ulanmagan hollarda ham ko'prik xizmatlari ishlay olishi uchun. Kimdir
kuchliroq (masalan Analytics parser_core) moslashtiruvchi ulamoqchi bo'lsa,
xuddi shu `MatchResult` shaklini qaytarishi kifoya — ko'prik xizmati
qaysi resolver ishlatilganidan qat'i nazar bir xil ishlaydi.
"""
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class MatchResult:
    ready: bool  # ishonchli moslik topilsa True
    matched_code: str | None = None  # topilgan external_code (yoki boshqa barqaror ID)
    matched_name: str | None = None  # topilgan nomning o'zi (audit uchun)
    confidence: float = 0.0  # 0..1
    reason: str | None = None  # ready=False bo'lsa, sababi


DEFAULT_CONFIDENCE_THRESHOLD = 0.72


def best_name_match(
    query: str,
    candidates: dict[str, str],
    *,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> MatchResult:
    """
    `candidates`: {external_code: name} — moslashtiriladigan nomzodlar.

    Eng yuqori o'xshashlikdagi nomzod threshold'dan past bo'lsa (yoki eng
    yaqin ikkita nomzod bir-biriga juda yaqin bo'lsa — chinakam noaniqlik),
    ready=False qaytadi. Bu "avtomatik yozilmaydi, owner tasdig'iga tushadi"
    qoidasini ta'minlaydi.
    """
    query = (query or "").strip().lower()
    if not query:
        return MatchResult(ready=False, reason="Qidiruv matni bo'sh")
    if not candidates:
        return MatchResult(ready=False, reason="Nomzodlar ro'yxati bo'sh")

    scored = sorted(
        (
            (SequenceMatcher(None, query, name.strip().lower()).ratio(), code, name)
            for code, name in candidates.items()
        ),
        key=lambda row: row[0],
        reverse=True,
    )
    best_score, best_code, best_name = scored[0]

    if best_score < threshold:
        return MatchResult(
            ready=False,
            confidence=best_score,
            reason=f"Eng yaqin moslik ('{best_name}') ishonch chegarasidan past ({best_score:.2f} < {threshold})",
        )

    if len(scored) > 1:
        second_score = scored[1][0]
        # Ikkita nomzod bir-biriga juda yaqin bo'lsa — bu chinakam noaniqlik,
        # tasodifiy ravishda birini tanlash xavfli.
        if best_score - second_score < 0.05:
            return MatchResult(
                ready=False,
                confidence=best_score,
                reason=(
                    f"Bir nechta nomzod bir xil darajada mos keladi "
                    f"('{best_name}' va '{scored[1][2]}') — noaniq"
                ),
            )

    return MatchResult(
        ready=True, matched_code=best_code, matched_name=best_name, confidence=best_score
    )
