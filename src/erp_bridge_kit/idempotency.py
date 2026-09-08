"""
Har bir avtomatik yozuv o'ziga xos, DETERMINISTIK source_id bilan yuborilishi
kerak — shu bilan qayta yuborilsa (masalan tarmoq uzilib, retry qilinganda)
maqsad modul (Ombor) buni duplicate deb tanib, ikkinchi marta qo'llamaydi.

Bu qoida barcha ko'prik xizmatlari (production-sync, kelajakdagi
finance-sync va h.k.) uchun bir xil bo'lishi kerak — shuning uchun shu
yerda markazlashtirilgan.
"""


def build_source_id(prefix: str, *parts: str) -> str:
    """
    Masalan: build_source_id("hr-task", "12345") -> "hr-task:12345"
             build_source_id("hr-task", "12345", "banka") -> "hr-task:12345:banka"

    Chaqiruvchi `parts` sifatida manba tizimidagi haqiqatan ham barqaror,
    o'zgarmas identifikatorlarni berishi kerak (masalan HR'ning task_id'si) —
    vaqt tamg'asi yoki tasodifiy qiymat EMAS, aks holda idempotentlik buziladi.
    """
    if not prefix or not prefix.strip():
        raise ValueError("prefix bo'sh bo'lishi mumkin emas")
    cleaned_parts = [str(p).strip() for p in parts if str(p).strip()]
    if not cleaned_parts:
        raise ValueError("kamida bitta part berilishi kerak")
    return ":".join([prefix.strip(), *cleaned_parts])
