"""
Preverjanje prenesenih podatkov:
  1. popolnost (manjkajoče vrednosti po letih),
  2. bilanca: proizvodnja − poraba ≈ neto čezmejni tok (izvoz − uvoz),
  3. kontrolne vrednosti za ročno primerjavo z ENTSO-E Transparency.

Zagon: .venv/bin/python src/preverjanje.py
"""

from pathlib import Path

import pandas as pd

KOREN = Path(__file__).resolve().parents[1]
DATA = KOREN / "data"

pro = pd.read_parquet(DATA / "proizvodnja.parquet")
mej = pd.read_parquet(DATA / "meje.parquet")
cen = pd.read_parquet(DATA / "cena.parquet")

print("Stolpci proizvodnje:", list(pro.columns))
print("Stolpci meja:", list(mej.columns))

# --- 1. popolnost -------------------------------------------------------------
print("\n1) Delež manjkajočih vrednosti po letih [%]")
glavni = ["Nuclear", "Fossil gas", "Solar", "Load"]
glavni = [c for c in glavni if c in pro.columns]
manj = pro[glavni].isna().groupby(pro.index.year).mean().mul(100).round(1)
manj["cena"] = cen["cena"].isna().groupby(cen.index.year).mean().mul(100).round(1)
manj["meje_sum"] = mej["sum"].isna().groupby(mej.index.year).mean().mul(100).round(1)
print(manj)

# --- 2. bilanca ---------------------------------------------------------------
print("\n2) Bilanca (urna povprečja, MW)")
viri = [c for c in pro.columns if c not in
        ("Load", "Residual load", "Renewable share of load",
         "Renewable share of generation", "Cross border electricity trading")]
h = pd.DataFrame({
    "proizvodnja": pro[viri].sum(axis=1, min_count=1),
    "poraba": pro["Load"],
}).resample("h").mean()
h["gen_minus_load"] = h["proizvodnja"] - h["poraba"]
# cbet je v GW in + = UVOZ; obrnemo predznak, da je neto_meje = izvoz − uvoz
h["neto_meje"] = -mej["sum"].resample("h").mean() * 1000
h = h.dropna()
h["razlika"] = h["gen_minus_load"] - h["neto_meje"]
let = h.groupby(h.index.year)[["proizvodnja", "poraba", "gen_minus_load", "neto_meje", "razlika"]].mean().round(0)
print(let)
print("Korelacija (gen−load) vs neto meje:", round(h["gen_minus_load"].corr(h["neto_meje"]), 3))

# --- 3. kontrolne vrednosti ---------------------------------------------------
print("\n3) Kontrolne vrednosti (za primerjavo z ENTSO-E, čas CET)")
loc = lambda df: df.tz_convert("Europe/Budapest")
p, m, c = loc(pro), loc(mej), loc(cen)
for ts in ["2026-11-05 18:00", "2026-11-05 12:00", "2025-01-15 08:00"]:
    t = pd.Timestamp(ts, tz="Europe/Budapest")
    vr = p.loc[t:t + pd.Timedelta("59min")].mean()
    mm = m.loc[t:t + pd.Timedelta("59min")].mean() * 1000
    cc = c.loc[t:t + pd.Timedelta("59min"), "cena"].mean()
    print(f"\n  {ts}:  cena {cc:.2f} EUR/MWh | poraba {vr.get('Load', float('nan')):.0f} MW | "
          f"jedrska {vr.get('Nuclear', float('nan')):.0f} MW | plin {vr.get('Fossil gas', float('nan')):.0f} MW | "
          f"sonce {vr.get('Solar', float('nan')):.0f} MW")
    print("   meje [MW, + = uvoz v HU, − = izvoz]:", {k: round(v) for k, v in mm.items() if pd.notna(v)})

t45 = c.loc["2026-11-02":"2026-11-08", "cena"].mean()
print(f"\n  Povprečna cena teden 45: {t45:.2f} EUR/MWh (naloga: 290.98)")
