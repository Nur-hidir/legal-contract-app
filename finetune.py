import csv
import json
import os
import sys

from langchain_community.document_loaders import PyPDFLoader

from ingest import madde_bazli_parcala

LAWS_DIR = os.path.join("data", "laws")
TASLAK_CSV = os.path.join("data", "egitim_taslak.csv")
EVAL_JSON = "eval_set.json"
TEMEL_MODEL = "intfloat/multilingual-e5-small"
MODEL_CIKTI = os.path.join("models", "e5-hukuk")
MIN_CIFT = 30


# ---------- ADIM 2: Eğitim verisi taslağını hazırla ----------
def hazirla():
    satirlar = []
    for ad in sorted(os.listdir(LAWS_DIR)):
        if not ad.lower().endswith(".pdf"):
            continue
        sayfalar = PyPDFLoader(os.path.join(LAWS_DIR, ad)).load()
        for p in madde_bazli_parcala(sayfalar, ad):
            madde = p.metadata.get("madde_no")
            if madde in ("Giriş", "Belirsiz"):
                continue
            metin = p.page_content
            if metin.startswith("[") and "\n" in metin:
                metin = metin.split("\n", 1)[1]
            satirlar.append([
                ad, madde, p.metadata.get("parca", 1), p.metadata.get("sayfa"),
                metin.strip(), "", "", "",
            ])

    os.makedirs("data", exist_ok=True)
    with open(TASLAK_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([
            "kanun", "madde_no", "parca", "sayfa", "kanun_metni",
            "sorgu_aykiri", "sorgu_uygun", "sorgu_soru",
        ])
        w.writerows(satirlar)
    print(f"{len(satirlar)} kanun parçası yazıldı: {TASLAK_CSV}")


# ---------- ADIM 3: Modelin arama başarısını ölç ----------
def olc():
    from sentence_transformers import SentenceTransformer

    model_adi = sys.argv[2] if len(sys.argv) > 2 else TEMEL_MODEL
    print(f"Model: {model_adi}")

    if not os.path.exists(EVAL_JSON):
        print(f"{EVAL_JSON} bulunamadı. Ana klasöre koy.")
        return
    with open(EVAL_JSON, encoding="utf-8") as f:
        veri = [o for o in json.load(f) if not o.get("kapsam_disi")]

    parcalar = []
    for ad in sorted(os.listdir(LAWS_DIR)):
        if ad.lower().endswith(".pdf"):
            sayfalar = PyPDFLoader(os.path.join(LAWS_DIR, ad)).load()
            parcalar.extend(madde_bazli_parcala(sayfalar, ad))
    print(f"{len(parcalar)} kanun parçası vektöre çevriliyor (CPU'da birkaç dakika sürebilir)...")

    model = SentenceTransformer(model_adi)
    pasajlar = model.encode(
        ["passage: " + p.page_content for p in parcalar],
        batch_size=16, normalize_embeddings=True, show_progress_bar=True,
    )
    sorgular = model.encode(
        ["query: " + o["madde"] for o in veri], normalize_embeddings=True,
    )

    skorlar = sorgular @ pasajlar.T
    SINIR = 10
    siralar = []

    print(f"\n{'Sıra':<6}Madde")
    print("-" * 80)
    for i, o in enumerate(veri):
        en_iyiler = skorlar[i].argsort()[::-1][:SINIR]
        sira = None
        for r, idx in enumerate(en_iyiler, start=1):
            d = parcalar[idx]
            if d.metadata.get("source") == o["kanun"] and d.metadata.get("madde_no") in o["madde_no"]:
                sira = r
                break
        siralar.append(sira)
        ilk = parcalar[en_iyiler[0]].metadata
        print(f"{str(sira or 'YOK'):<6}{o['madde'][:55]}  -> ilk: {ilk.get('madde_no')}")

    n = len(siralar)
    print(f"\n=== SONUÇ ({n} örnek) ===")
    for k in (1, 3, 5):
        isabet = sum(1 for s in siralar if s and s <= k)
        print(f"Recall@{k}: {isabet}/{n} (%{100 * isabet / n:.0f})")
    mrr = sum(1 / s for s in siralar if s) / n
    print(f"MRR      : {mrr:.3f}")


# ---------- ADIM 4: Modeli eğit ----------
def egit():
    from datasets import Dataset
    from sentence_transformers import (
        SentenceTransformer,
        SentenceTransformerTrainer,
        SentenceTransformerTrainingArguments,
        losses,
    )
    from sentence_transformers.training_args import BatchSamplers

    if not os.path.exists(TASLAK_CSV):
        print(f"{TASLAK_CSV} bulunamadı. Önce: python finetune.py hazirla")
        return

    # Test sorularının eğitime sızmaması için eval_set.json cümlelerini dışarıda tut
    yasak = set()
    if os.path.exists(EVAL_JSON):
        with open(EVAL_JSON, encoding="utf-8") as f:
            yasak = {o["madde"].strip() for o in json.load(f)}

    with open(TASLAK_CSV, encoding="utf-8-sig", newline="") as f:
        ilk_satir = f.readline()
        ayirici = ";" if ilk_satir.count(";") > ilk_satir.count(",") else ","
        f.seek(0)
        satirlar = list(csv.DictReader(f, delimiter=ayirici))

    sorgular, pozitifler, atilan = [], [], 0
    for s in satirlar:
        metin = (s.get("kanun_metni") or "").strip()
        if not metin:
            continue
        # app/olc ile aynı biçim: başlık satırı + metin
        pasaj = "passage: " + f"[{s['kanun']} - {s['madde_no']}]\n" + metin
        for sutun in ("sorgu_aykiri", "sorgu_uygun", "sorgu_soru"):
            q = (s.get(sutun) or "").strip()
            if not q:
                continue
            if q in yasak:
                atilan += 1
                continue
            sorgular.append("query: " + q)
            pozitifler.append(pasaj)

    print(f"{len(sorgular)} eğitim çifti bulundu ({atilan} tanesi test setiyle aynı olduğu için atıldı).")
    if len(sorgular) < MIN_CIFT:
        print(f"En az {MIN_CIFT} dolu çift gerekli. {TASLAK_CSV} dosyasındaki sorgu sütunlarını doldur.")
        return

    model = SentenceTransformer(TEMEL_MODEL)
    veri = Dataset.from_dict({"anchor": sorgular, "positive": pozitifler})
    kayip = losses.MultipleNegativesRankingLoss(model)

    args = SentenceTransformerTrainingArguments(
        output_dir=os.path.join("models", "kontrol"),
        num_train_epochs=4,
        per_device_train_batch_size=16,
        learning_rate=2e-5,
        warmup_ratio=0.1,
        batch_sampler=BatchSamplers.NO_DUPLICATES,  # aynı maddeyi aynı grupta iki kez görmesin
        save_strategy="no",
        logging_steps=5,
        report_to="none",
    )
    trainer = SentenceTransformerTrainer(
        model=model, args=args, train_dataset=veri, loss=kayip,
    )
    trainer.train()

    os.makedirs("models", exist_ok=True)
    model.save_pretrained(MODEL_CIKTI)
    print(f"\nEğitilen model kaydedildi: {MODEL_CIKTI}")
    print(f"Puanı ölçmek için: python finetune.py olc {MODEL_CIKTI}")


KOMUTLAR = {
    "hazirla": hazirla,
    "olc": olc,
    "egit": egit,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in KOMUTLAR:
        print("Kullanım: python finetune.py <komut>")
        print("Komutlar:", ", ".join(KOMUTLAR))
        sys.exit(1)
    KOMUTLAR[sys.argv[1]]()