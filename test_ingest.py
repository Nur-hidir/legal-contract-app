import os
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from ingest import madde_bazli_parcala

load_dotenv()

PDF_YOLLARI = ["is_kanunu.pdf"]  # kendi PDF yolların
K = 5

# ÖRNEK: Bunlar sadece şablon. Gerçek kanun metnine bakıp kendin doğrula.
TEST_SETI = [
    {
        "madde": "Haftalık çalışma süresi 50 saattir ve fazla çalışma için ek ücret ödenmez.",
        "kanuna_aykiri_mi": "Evet",
        "kanun_dosyasi": "is_kanunu.pdf",
        "dogru_madde": "Madde 41",
    },
    {
        "madde": "İşveren, işçiyi önceden haber vermeden istediği zaman işten çıkarabilir.",
        "kanuna_aykiri_mi": "Evet",
        "kanun_dosyasi": "is_kanunu.pdf",
        "dogru_madde": "Madde 17",
    },
    {
        "madde": "İşçi her yıl 3 gün ücretli izin kullanır.",
        "kanuna_aykiri_mi": "Evet",
        "kanun_dosyasi": "is_kanunu.pdf",
        "dogru_madde": "Madde 53",
    },
]


def db_olustur():
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=os.getenv("GEMINI_API_KEY"),
    )
    parcalar = []
    for yol in PDF_YOLLARI:
        sayfalar = PyPDFLoader(yol).load()
        parcalar.extend(madde_bazli_parcala(sayfalar, os.path.basename(yol)))
    print(f"{len(parcalar)} parça oluşturuldu.")
    return FAISS.from_documents(parcalar, embeddings)


def ilk_dogru_sira(sonuclar, ornek):
    for sira, doc in enumerate(sonuclar, start=1):
        if (doc.metadata.get("madde_no") == ornek["dogru_madde"]
                and doc.metadata.get("source") == ornek["kanun_dosyasi"]):
            return sira
    return None


def main():
    db = db_olustur()
    siralar = []
    kacirilanlar = []

    for ornek in TEST_SETI:
        sonuclar = db.similarity_search(ornek["madde"], k=K)
        sira = ilk_dogru_sira(sonuclar, ornek)
        siralar.append(sira)
        if sira is None:
            gelenler = [d.metadata.get("madde_no") for d in sonuclar]
            kacirilanlar.append((ornek["madde"][:60], ornek["dogru_madde"], gelenler))

    toplam = len(TEST_SETI)

    def recall(k):
        return sum(1 for s in siralar if s is not None and s <= k) / toplam

    mrr = sum(1 / s for s in siralar if s is not None) / toplam

    print("\n--- SONUÇLAR ---")
    print(f"Test sayısı : {toplam}")
    print(f"Recall@1    : %{recall(1) * 100:.0f}")
    print(f"Recall@3    : %{recall(3) * 100:.0f}")
    print(f"Recall@5    : %{recall(5) * 100:.0f}")
    print(f"MRR         : {mrr:.2f}")

    if kacirilanlar:
        print("\n--- BULUNAMAYANLAR ---")
        for metin, dogru, gelenler in kacirilanlar:
            print(f"- {metin}...\n  beklenen: {dogru} | gelenler: {gelenler}")


if __name__ == "__main__":
    main()