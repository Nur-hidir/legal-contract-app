import re
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
# YENİ EKLENEN SATIR
from langchain_community.embeddings import HuggingFaceEmbeddings 

# "Madde 17 -", "MADDE 17-", "Geçici Madde 1", "Ek Madde 2" gibi başlıkları yakalar
MADDE_REGEX = re.compile(
    r"(?m)^[ \t]*((?:EK|Ek|GEÇİCİ|Geçici|GECICI)[ \t]+)?(?:MADDE|Madde)[ \t]+(\d+)[ \t]*[-–—.:]?"
)

# Çok uzun maddeler için ikinci seviye bölücü
UZUN_MADDE_BOLUCU = RecursiveCharacterTextSplitter(
    separators=["\n\n", "\n", ".", " ", ""],
    chunk_size=1500,
    chunk_overlap=150,
)


def _sayfa_haritasi(sayfalar):
    """Tüm sayfaları tek metinde birleştirir, her sayfanın başlangıç ofsetini tutar."""
    tam_metin = ""
    ofsetler = []  # (baslangic_ofset, sayfa_no)
    for i, sayfa in enumerate(sayfalar):
        ofsetler.append((len(tam_metin), sayfa.metadata.get("page", i) + 1))
        tam_metin += sayfa.page_content + "\n"
    return tam_metin, ofsetler


def _sayfa_bul(ofsetler, konum):
    sayfa_no = ofsetler[0][1]
    for baslangic, no in ofsetler:
        if baslangic <= konum:
            sayfa_no = no
        else:
            break
    return sayfa_no


def madde_bazli_parcala(sayfalar, kanun_adi):
    """
    PyPDFLoader'dan gelen sayfa listesini madde bazlı Document parçalarına çevirir.
    Metadata: source (kanun adı), madde_no, sayfa
    """
    tam_metin, ofsetler = _sayfa_haritasi(sayfalar)
    eslesmeler = list(MADDE_REGEX.finditer(tam_metin))

    # Madde başlığı bulunamazsa genel bölücüye dön
    if not eslesmeler:
        parcalar = UZUN_MADDE_BOLUCU.split_documents(sayfalar)
        for p in parcalar:
            p.metadata["source"] = kanun_adi
            p.metadata["madde_no"] = "Belirsiz"
            p.metadata["sayfa"] = p.metadata.get("page", 0) + 1
        return parcalar

    sonuc = []

    # İlk maddeden önceki giriş kısmı (kanun başlığı, amaç vb.)
    giris = tam_metin[: eslesmeler[0].start()].strip()
    if giris:
        sonuc.append(
            Document(
                page_content=giris,
                metadata={"source": kanun_adi, "madde_no": "Giriş", "sayfa": ofsetler[0][1]},
            )
        )

    for i, m in enumerate(eslesmeler):
        bitis = eslesmeler[i + 1].start() if i + 1 < len(eslesmeler) else len(tam_metin)
        metin = tam_metin[m.start():bitis].strip()
        if not metin:
            continue

        onek = (m.group(1) or "").strip().title()
        madde_no = f"{onek} Madde {m.group(2)}".strip()
        sayfa_no = _sayfa_bul(ofsetler, m.start())

        # Her parçanın başına kanun ve madde bilgisini ekle: embedding aramasına da yardımcı olur
        baslik = f"[{kanun_adi} {madde_no}]\n"

        if len(metin) <= 1500:
            parcalar = [metin]
        else:
            parcalar = UZUN_MADDE_BOLUCU.split_text(metin)

        for j, parca in enumerate(parcalar):
            sonuc.append(
                Document(
                    page_content=baslik + parca,
                    metadata={
                        "source": kanun_adi,
                        "madde_no": madde_no,
                        "sayfa": sayfa_no,
                        "parca": j + 1,
                    },
                )
            )

    return sonuc


def sozlesme_maddelerine_ayir(metin):
    """Sözleşme metnini '1. BAŞLIK', '14. CEZAİ ŞART', 'Madde 3' gibi numaralı maddelere böler."""
    desen = r"(?=(?<![\w.])(?:(?:MADDE|Madde)\s+)?\d{1,2}\s*[.)\-–]\s*[A-ZÇĞİÖŞÜ])"
    parcalar = [p.strip() for p in re.split(desen, metin) if len(p.strip()) > 20]
    return parcalar if len(parcalar) > 1 else [metin.strip()]