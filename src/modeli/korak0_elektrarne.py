"""
Korak 0: pregled vseh vrst elektrarn na Madžarskem (vse elektrarne iste vrste skupaj).

Za vsako vrsto: nameščena moč, proizvedena energija, delež – in najpomembnejše za
napoved: KAKO ZELO NIHA iz tedna v teden in kako je to povezano z neto pozicijo.
Za napoved ni pomembno, kdo proizvede največ, ampak kdo se najbolj spreminja.

Zagon: .venv/bin/python src/modeli/korak0_elektrarne.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analiza"))
from analiza_a import DATA, preberi

VRSTE = {   # naše ime: stolpci Energy-Charts
    "Jedrska (Paks)": ["Nuclear"],
    "Plin": ["Fossil gas"],
    "Sonce": ["Solar"],
    "Premog (lignit)": ["Fossil brown coal / lignite", "Fossil hard coal"],
    "Biomasa in odpadki": ["Biomass", "Waste"],
    "Veter": ["Wind onshore"],
    "Hidro": ["Hydro Run-of-River", "Hydro water reservoir"],
    "Ostalo (olje, drugo)": ["Fossil oil", "Others", "Other renewables", "Geothermal"],
}
MOC = {     # nameščena moč (namescena_moc.parquet): naše ime: stolpci
    "Jedrska (Paks)": ["Nuclear"], "Plin": ["Fossil gas"], "Sonce": ["Solar AC"],
    "Premog (lignit)": ["Fossil brown coal / lignite", "Fossil hard coal"],
    "Biomasa in odpadki": ["Biomass", "Waste"], "Veter": ["Wind onshore"],
    "Hidro": ["Hydro Run-of-River", "Hydro water reservoir"],
    "Ostalo (olje, drugo)": ["Fossil oil", "Others", "Other renewables", "Geothermal"],
}

if __name__ == "__main__":
    p = preberi("proizvodnja.parquet")
    m = preberi("meje.parquet")
    df = pd.DataFrame({ime: p[st].sum(axis=1, min_count=1) for ime, st in VRSTE.items()})
    df["Poraba"] = p["Load"]
    df["Neto"] = -m["sum"].reindex(df.index) * 1000
    df = df[df.index >= "2023-01-02"]                       # zadnja ~4 leta

    moc = pd.read_parquet(DATA / "namescena_moc.parquet").loc["2025"]
    l25 = df[df.index.year == 2025]
    energija = l25.drop(columns=["Neto"]).mean() * len(l25) / 4 / 1e6   # TWh
    proizv = energija.drop("Poraba").sum()

    # tedenska povprečja (pon–ned) in sprememba iz tedna v teden
    teden = df.resample("W-SUN").mean().iloc[1:-1]
    sprem = teden.diff().dropna()

    t = pd.DataFrame({
        "nameščena moč 2025 [GW]": pd.Series({k: moc[v].sum() for k, v in MOC.items()}),
        "energija 2025 [TWh]": energija,
        "delež proizvodnje 2025 [%]": energija / proizv * 100,
        "povprečje 2023–26 [MW]": df.mean(),
        "nihanje teden→teden [MW]": sprem.abs().mean(),
        "največja sprememba [MW]": sprem.abs().max(),
        "povezava z neto (korelacija sprememb)": sprem.corrwith(sprem["Neto"]),
    }).drop(index="Neto")
    t.loc["Poraba", "delež proizvodnje 2025 [%]"] = float("nan")
    t = t.sort_values("nihanje teden→teden [MW]", ascending=False)
    print("Vrste elektrarn na Madžarskem – vse elektrarne iste vrste skupaj")
    print("Obdobje 2. 1. 2023 – 15. 11. 2026, tedenska povprečja 15-min vrednosti (pon–ned, "
          "lokalni čas).")
    print("Nihanje = povprečna absolutna sprememba tedenskega povprečja od tedna do tedna.")
    print("Korelacija: + = ko vrsta zraste, se neto poveča (manj uvoza).\n")
    print(t.round(2).to_string())
    print(f"\nZa primerjavo: neto pozicija sama niha teden→teden povprečno "
          f"{sprem['Neto'].abs().mean():.0f} MW.")
    t.round(3).to_csv(DATA / "korak0_elektrarne.csv")
