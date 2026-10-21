from rules import kural_kontrol

def seviyeler(metin):
    return [(b["madde"], b["seviye"]) for b in kural_kontrol(metin)]

t1 = "Çalışan, haftalık 45 saati aşan çalışmaları için ayrıca ücret talep edemez; fazla mesai ücreti maaşa dahildir ve ek bir ödeme yapılmaz."
t2 = "İşveren, çalışanın iş sözleşmesini herhangi bir gerekçe göstermeksizin ve yalnızca bir gün önceden haber vererek sona erdirebilir."
t3 = "Çalışan, işten ayrıldıktan sonra 10 yıl boyunca Türkiye'de hiçbir şirkette aynı alanda çalışamaz."
t4 = "Çalışan, çalıştığı süre boyunca yıllık ücretli izin hakkından yararlanamaz."
t5 = "Çalışanın haftalık çalışma süresi 45 saattir ve haftada 5 iş günü olarak uygulanır."
t6 = "Taraflar bu sözleşmeyi iki nüsha olarak düzenlemiş ve imzalamıştır."
t7 = "İşveren, iş sözleşmesini sona erdirmeden önce çalışana iki hafta önceden yazılı bildirimde bulunur."
t8 = "Telafi çalışması fazla sürelerle çalışma veya fazla çalışma sayılmaz, karşılığında fazla sürelerle çalışma veya fazla çalışma ücreti ödenmez."

for ad, metin in [("t1", t1), ("t2", t2), ("t3", t3), ("t4", t4), ("t5", t5), ("t6", t6), ("t7", t7), ("t8", t8)]:
    print(ad, seviyeler(metin))

assert seviyeler(t1) == [("Madde 41", "aykiri")], seviyeler(t1)
assert seviyeler(t2) == [("Madde 17", "aykiri")], seviyeler(t2)
assert seviyeler(t3) == [("Madde 445", "aykiri")], seviyeler(t3)
assert seviyeler(t4) == [("Madde 53", "aykiri")], seviyeler(t4)
assert seviyeler(t5) == [], seviyeler(t5)
assert seviyeler(t6) == [], seviyeler(t6)
assert seviyeler(t7) == [("Madde 17", "uyari")], seviyeler(t7)
assert seviyeler(t8) == [], seviyeler(t8)
print("TÜM TESTLER GEÇTİ")
