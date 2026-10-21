import re

# Bu dosya yapay zekâ kullanmaz. Basit, kesin kuralları kontrol eder.
# Madde numaralarını kendi kanun dosyalarınla karşılaştırıp doğrula.

SAYILAR = {
    "bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6,
    "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10, "on iki": 12,
    "on beş": 15, "yirmi": 20, "otuz": 30,
}
BIRIM_GUN = {"gün": 1, "hafta": 7, "ay": 30, "yıl": 365, "sene": 365}

_sayi_deseni = "|".join(sorted(map(re.escape, SAYILAR), key=len, reverse=True))
SURE_RE = re.compile(
    rf"(?<![a-zçğıöşü0-9])(\d+|{_sayi_deseni})\s*(gün|hafta|ay|yıl|sene)"
    r"(?:lık|lik|luk|lük)?(?![a-zçğıöşü])"
)


def kucult(metin):
    return metin.replace("İ", "i").replace("I", "ı").lower()


def cumlelere_ayir(metin):
    return [c.strip() for c in re.split(r"[.;\n]+", kucult(metin)) if c.strip()]


def sureler(cumle):
    """Cümledeki süreleri gün cinsinden döndürür (örn. 'iki hafta' -> 14)."""
    sonuc = []
    for m in SURE_RE.finditer(cumle):
        sayi = m.group(1)
        deger = int(sayi) if sayi.isdigit() else SAYILAR[sayi]
        sonuc.append(deger * BIRIM_GUN[m.group(2)])
    return sonuc


def _var(cumle, parcalar):
    return any(p in cumle for p in parcalar)


def _bulgu(seviye, kanun, madde, aciklama):
    return {"seviye": seviye, "kanun": kanun, "madde": madde, "aciklama": aciklama}


def _en_ciddi(bulgular):
    for b in bulgular:
        if b["seviye"] == "aykiri":
            return b
    return bulgular[0] if bulgular else None


def kural_ihbar(cumleler):
    bulgular = []
    for c in cumleler:
        if _var(c, ["haber ver", "bildirim", "ihbar", "önceden"]) and \
           _var(c, ["fesh", "sona er", "işten çıkar", "iş sözleşmesini"]):
            ds = sureler(c)
            if not ds:
                continue
            gun = ds[0]
            if gun < 14:
                bulgular.append(_bulgu(
                    "aykiri", "4857 sayılı İş Kanunu", "Madde 17",
                    "Bildirim süresi en az 2 haftadır (çalışma süresine göre 2 ile 8 hafta arası). "
                    "Sözleşmeyle bunun altına inilemez.",
                ))
            elif gun < 56:
                bulgular.append(_bulgu(
                    "uyari", "4857 sayılı İş Kanunu", "Madde 17",
                    "Çalışma süresi 3 yılı aşıyorsa bildirim süresi en az 8 haftadır. "
                    "Bu süre kıdeme göre yetersiz kalabilir.",
                ))
    return _en_ciddi(bulgular)


def kural_rekabet(cumleler):
    bulgular = []
    for c in cumleler:
        if _var(c, ["rekabet", "aynı alanda", "aynı sektör"]) and \
           _var(c, ["ayrıl", "sona erme", "sonra"]):
            ds = sureler(c)
            if ds and max(ds) > 730:
                bulgular.append(_bulgu(
                    "aykiri", "Türk Borçlar Kanunu", "Madde 445",
                    "İşten ayrıldıktan sonraki rekabet yasağı, özel durumlar dışında en fazla 2 yıl olabilir.",
                ))
    return _en_ciddi(bulgular)


def kural_fazla_mesai(cumleler):
    bulgular = []
    kesin = re.compile(
        r"(ayrıca\s+)?ücret\s+talep\s+edemez|ek\s+(bir\s+)?ödeme\s+yapılmaz|ödenmez|karşılık\s+talep\s+edemez"
    )
    for c in cumleler:
        if "telafi" in c:
            continue
        if _var(c, ["fazla mesai", "fazla çalışma", "mesai ücreti", "45 saati aş"]) or \
           ("45 saat" in c and "aş" in c):
            if kesin.search(c):
                bulgular.append(_bulgu(
                    "aykiri", "4857 sayılı İş Kanunu", "Madde 41",
                    "Haftada 45 saati aşan her çalışma saati için normal ücretin %50 fazlası ödenmelidir. "
                    "Bu hak sözleşmeyle kaldırılamaz.",
                ))
            elif _var(c, ["maaşa dahil", "ücrete dahil", "maaşa dâhil"]):
                bulgular.append(_bulgu(
                    "uyari", "4857 sayılı İş Kanunu", "Madde 41",
                    "Fazla mesai ücretinin maaşa dahil sayılması sınırlı durumlarda kabul edilir. "
                    "Zamlı ödeme hakkı yine de korunmalıdır.",
                ))
    return _en_ciddi(bulgular)


def kural_yillik_izin(cumleler):
    bulgular = []
    for c in cumleler:
        if "yıllık" in c and "izin" in c and _var(c, [
            "hakkı yoktur", "yararlanamaz", "kullanamaz", "vazgeç",
            "hakkı bulunmamakta", "hak talep edemez",
        ]):
            bulgular.append(_bulgu(
                "aykiri", "4857 sayılı İş Kanunu", "Madde 53",
                "Yıllık ücretli izin hakkı kaldırılamaz ve bu haktan vazgeçilemez.",
            ))
    return _en_ciddi(bulgular)


KURALLAR = [kural_ihbar, kural_rekabet, kural_fazla_mesai, kural_yillik_izin]


def kural_kontrol(metin):
    """Sözleşme maddesine uygulanan kuralların bulgularını liste olarak döndürür."""
    cumleler = cumlelere_ayir(metin)
    sonuc = []
    for kural in KURALLAR:
        bulgu = kural(cumleler)
        if bulgu:
            sonuc.append(bulgu)
    return sonuc
