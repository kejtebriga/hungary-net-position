"""
Primerjava podatkov Energy-Charts (data/*.parquet) z uradnimi podatki ENTSO-E (data/entsoe/).

Za vsako količino na urni ravni v skupnem obdobju izračuna:
  povprečje v obeh virih, povprečno absolutno razliko (MAE), relativno razliko in korelacijo.
Rezultat: izpis + data/entsoe/primerjava.csv

Zagon: .venv/bin/python src/podatki/primerjava_virov.py
"""

from pathlib import Path

import pandas as pd

KOREN = Path(__file__).resolve().parents[2]
D, E = KOREN / "data", KOREN / "data" / "entsoe"


def urno(s: pd.Series) -> pd.Series:
    return s.resample("h").mean()


ec_pro = pd.read_parquet(D / "proizvodnja.parquet")
ec_mej = pd.read_parquet(D / "meje.parquet") * 1000  # GW -> MW, + = uvoz
ec_cen = pd.read_parquet(D / "cena.parquet")

en_pro = pd.read_parquet(E / "proizvodnja.parquet")
en_por = pd.read_parquet(E / "poraba.parquet")
en_cen = pd.read_parquet(E / "cena.parquet")
en_izm = pd.read_parquet(E / "izmenjave.parquet")
en_fiz = pd.read_parquet(E / "fizicni_tokovi.parquet")

pari = {"Cena [EUR/MWh]": (ec_cen["cena"], en_cen["cena"]),
        "Poraba (Load)": (ec_pro["Load"], en_por["Load"])}
for vir in ["Nuclear", "Fossil gas", "Fossil brown coal / lignite", "Solar",
            "Wind onshore", "Biomass"]:
    if vir in en_pro and vir in ec_pro:
        pari[vir] = (ec_pro[vir], en_pro[vir])
IMENA = {"Austria": "AT", "Slovakia": "SK", "Romania": "RO", "Croatia": "HR",
         "Serbia": "RS", "Slovenia": "SI", "Ukraine": "UA", "sum": "sum"}
for ec_ime, kr in IMENA.items():
    if kr in en_izm:
        pari[f"Meja {kr}: trgovanje"] = (ec_mej[ec_ime], en_izm[kr])
    if kr in en_fiz:
        pari[f"Meja {kr}: fizični tok (za primerjavo)"] = (ec_mej[ec_ime], en_fiz[kr])

vrstice = []
for ime, (a, b) in pari.items():
    df = pd.concat([urno(a).rename("ec"), urno(b).rename("en")], axis=1).dropna()
    if df.empty:
        continue
    mae = (df.ec - df.en).abs().mean()
    vrstice.append({
        "količina": ime, "ur": len(df),
        "Energy-Charts": round(df.ec.mean(), 1), "ENTSO-E": round(df.en.mean(), 1),
        "povp. abs. razlika": round(mae, 1),
        "rel. razlika [%]": round(100 * mae / max(df.en.abs().mean(), 1e-9), 2),
        "korelacija": round(df.ec.corr(df.en), 4),
    })
tab = pd.DataFrame(vrstice).set_index("količina")
pd.set_option("display.width", 200)
print(tab.to_string())
tab.to_csv(E / "primerjava.csv", sep=";", decimal=",", encoding="utf-8-sig")

# kontrola: povprečna cena teden 45 po ENTSO-E
c = en_cen["cena"].tz_convert("Europe/Budapest").loc["2026-11-02":"2026-11-08"]
print(f"\nCena teden 45 po ENTSO-E: {c.mean():.2f} EUR/MWh (naloga: 290.98)")
