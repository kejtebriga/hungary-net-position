"""
Izvoz podatkov v CSV za ogled v Excelu (mapa data/za_ogled/).

- čas je v srednjeevropskem času (Europe/Budapest = CET/CEST), za primerjavo z ENTSO-E
- ločilo ';' in decimalna vejica (slovenske nastavitve Excela), kodiranje UTF-8 z BOM
- vse vrednosti so urna povprečja v MW (cena v EUR/MWh, temperatura v °C)

Zagon: .venv/bin/python src/podatki/izvoz_csv.py
"""

from pathlib import Path

import pandas as pd

KOREN = Path(__file__).resolve().parents[2]
DATA = KOREN / "data"
IZHOD = DATA / "za_ogled"
IZHOD.mkdir(exist_ok=True)

pro = pd.read_parquet(DATA / "proizvodnja.parquet")
mej = pd.read_parquet(DATA / "meje.parquet")
cen = pd.read_parquet(DATA / "cena.parquet")
vre = pd.read_parquet(DATA / "vreme.parquet")

# --- urna tabela --------------------------------------------------------------
VIRI = {
    "jedrska": ["Nuclear"],
    "plin": ["Fossil gas"],
    "lignit_premog": ["Fossil brown coal / lignite", "Fossil hard coal"],
    "sonce": ["Solar"],
    "veter": ["Wind onshore"],
    "biomasa": ["Biomass"],
    "voda": ["Hydro Run-of-River", "Hydro water reservoir"],
    "drugo": ["Others", "Other renewables", "Waste", "Fossil oil", "Geothermal"],
}
h = pd.DataFrame(index=pro.resample("h").mean().index)
p_h = pro.resample("h").mean()
for ime, stolpci in VIRI.items():
    h[ime] = p_h[[c for c in stolpci if c in p_h]].sum(axis=1, min_count=1)
h["proizvodnja_skupaj"] = h[list(VIRI)].sum(axis=1, min_count=1)
h["poraba"] = p_h["Load"]
h["neto_pozicija"] = h["proizvodnja_skupaj"] - h["poraba"]  # + = izvoz, − = uvoz

# meje: v virih + = uvoz → obrnemo, da je + = izvoz (enako kot neto pozicija)
m_h = -mej.resample("h").mean() * 1000
IMENA_MEJ = {"Austria": "meja_AT", "Slovakia": "meja_SK", "Romania": "meja_RO",
             "Croatia": "meja_HR", "Serbia": "meja_RS", "Slovenia": "meja_SI",
             "Ukraine": "meja_UA", "sum": "meje_skupaj"}
h = h.join(m_h.rename(columns=IMENA_MEJ)[list(IMENA_MEJ.values())])
h["cena"] = cen["cena"].resample("h").mean()
h["temperatura"] = vre["temperature_2m"]
h["soncno_sevanje"] = vre["shortwave_radiation"]

h = h.round(1)
h.index = h.index.tz_convert("Europe/Budapest").tz_localize(None)
h.index.name = "cas_CET"


def shrani(df: pd.DataFrame, ime: str) -> None:
    pot = IZHOD / ime
    df.to_csv(pot, sep=";", decimal=",", encoding="utf-8-sig")
    print(f"  {pot.relative_to(KOREN)}: {len(df):,} vrstic")


shrani(h.loc["2024-01-01":], "urno_2024_2026.csv")
shrani(h.loc["2026-11-02":"2026-11-08"], "teden_45.csv")
shrani(h.loc["2026-11-09":"2026-11-15"], "teden_46.csv")

# --- letna povprečja ----------------------------------------------------------
letno = h.drop(columns=["temperatura", "soncno_sevanje"]).groupby(h.index.year).mean().round(0)
letno["temperatura"] = h["temperatura"].groupby(h.index.year).mean().round(1)
letno.index.name = "leto"
shrani(letno, "letno.csv")

# --- kratka legenda -----------------------------------------------------------
(IZHOD / "PREBERI_ME.txt").write_text(
    "Podatki za Madžarsko (vir: Energy-Charts / ENTSO-E, vreme: Open-Meteo)\n\n"
    "cas_CET          : začetek ure, srednjeevropski čas\n"
    "jedrska ... drugo: proizvodnja po virih [MW, urno povprečje]\n"
    "poraba           : poraba (Load) [MW]\n"
    "neto_pozicija    : proizvodnja − poraba [MW]; + = izvoz, − = uvoz\n"
    "meja_XX          : neto tok čez mejo [MW]; + = izvoz iz HU, − = uvoz v HU\n"
    "meje_skupaj      : vsota vseh meja (≈ neto_pozicija)\n"
    "cena             : dan-vnaprej cena HU [EUR/MWh]\n"
    "temperatura      : tehtano povprečje 5 mest [°C]\n"
    "soncno_sevanje   : tehtano povprečje 5 mest [W/m²]\n",
    encoding="utf-8")
print("Končano.")
