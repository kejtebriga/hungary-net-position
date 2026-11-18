"""
b) Izbira modela, razpon in grafi – iz rezultatov modeli_b.py.

Pravilo izbire (določeno vnaprej): najmanjša napaka tedenskega povprečja v testu;
če sta dva modela praktično enaka (razlika < 5 MW), odloči jesen (okt–dec), ker je
teden 47 jesenski. Razpon = 10. in 90. percentil napak izbranega modela v tednih okt–dec.
Primerjava z dejanskimi dnevi tedna 47 je ločen, zadnji korak (po zamrznitvi).

Zagon: .venv/bin/python src/modeli/izbira_b.py
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modeli_b import IMENA, T47
from napoved_b import DATA, KOREN, TZ
from analiza_a import PALETA, shrani

FIG_B = KOREN / "figures" / "b"
SKUPINA = {"1": 0, "2": 0, "3a": 0, "3b": 0, "3c": 0, "4": 1, "5": 1, "6": 1, "7": 1,
           "8": 2, "9": 2, "10a": 2, "10b": 2, "11": 2, "12": 2, "12p": 2, "13": 3, "14": 3}
IME_SKUPINE = ["preprosti", "en dejavnik", "vse skupaj", "kombinacije"]

if __name__ == "__main__":
    pd.set_option("display.width", 200)
    R = pd.read_parquet(DATA / "b_modeli_test.parquet")
    e15 = pd.read_parquet(DATA / "b_modeli_napake15.parquet")
    dn = pd.read_parquet(DATA / "b_napovedi_t47_dnevno.parquet")
    q = pd.read_parquet(DATA / "b_napovedi_t47_15min.parquet")

    vsi = R.groupby("model")["napaka_teden"].apply(lambda e: e.abs().mean())
    jes = R[R["teden"].dt.month.isin([10, 11, 12])].groupby("model")["napaka_teden"] \
        .apply(lambda e: e.abs().mean())
    prva = vsi.nsmallest(2)
    izbran = prva.index[0]
    if prva.iloc[1] - prva.iloc[0] < 5:
        izbran = jes[prva.index].idxmin()
    print(f"Najmanjša napaka (vsi tedni): {prva.round(1).to_dict()}; okt–dec: "
          f"{jes[prva.index].round(1).to_dict()} → IZBRAN model {izbran} ({IMENA[izbran]})")

    # razpon iz jesenskih napak izbranega modela
    r = R[(R["model"] == izbran) & R["teden"].dt.month.isin([10, 11, 12])]
    q10, q90 = r["napaka_teden"].quantile([0.1, 0.9])
    sr = dn.loc["TEDEN 47", izbran]
    print(f"Teden 47: {sr:.0f} MW; razpon 80 % (okt–dec, {len(r)} tednov): "
          f"{sr + q10:.0f} do {sr + q90:.0f} MW; povprečna napaka teh tednov "
          f"{r['napaka_teden'].mean():+.0f} MW")
    jes15 = e15[e15["teden"].dt.month.isin([10, 11, 12])]
    pas = jes15.groupby(jes15.index.hour)[izbran].quantile([0.1, 0.9]).unstack()
    prof = pd.DataFrame({"napoved": q[izbran]})
    prof["spodaj"] = prof["napoved"] + pas[0.1].reindex(prof.index.hour).values
    prof["zgoraj"] = prof["napoved"] + pas[0.9].reindex(prof.index.hour).values
    peak = (prof.index.day_of_week < 5) & (prof.index.hour >= 8) & (prof.index.hour < 20)
    print(f"  base {prof['napoved'].mean():.0f} MW | peak (pon–pet 8–20) "
          f"{prof.loc[peak, 'napoved'].mean():.0f} | offpeak {prof.loc[~peak, 'napoved'].mean():.0f}"
          f" | energija tedna {prof['napoved'].sum() / 4 / 1000:.0f} GWh")
    prof.round(1).to_csv(KOREN / "report" / "napoved_t47_izbrani.csv")

    # --- GRAF b3: relativna napaka modelov (glede na naivni)
    rel = (vsi / vsi["1"]).sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    y = np.arange(len(rel))
    for s in range(4):
        m = [i for i in rel.index if SKUPINA[i] == s]
        ax.barh([list(rel.index).index(i) for i in m], rel[m], color=PALETA[s],
                height=0.7, label=IME_SKUPINE[s])
    ax.set_yticks(y, [f"{i} {IMENA[i]}" for i in rel.index], fontsize=7.5)
    ax.axvline(1, color="#333333", lw=1, ls="--")
    for yi, v in zip(y, rel.values):
        ax.text(v + 0.01, yi, f"{v:.2f}", va="center", fontsize=7)
    ax.set_xlabel("napaka tedna glede na naivni model (manj = bolje)")
    ax.set_xlim(0, 1.5)
    ax.set_title("Test 202 tednov: kateri model najbolje napove neto pozicijo", pad=22)
    ax.legend(ncol=4, loc="lower center", bbox_to_anchor=(0.45, 1.0), fontsize=7.5)
    ax.grid(axis="y", visible=False)
    shrani(fig, "b3_primerjava_modelov", FIG_B)

    # --- GRAF b1: profil izbranega modela s pasom
    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    x = np.arange(len(prof)) / 96
    ax.fill_between(x, prof["spodaj"], prof["zgoraj"], color=PALETA[0], alpha=0.18, lw=0,
                    label="razpon (10–90 %)")
    ax.plot(x, prof["napoved"], color=PALETA[0], lw=1.4,
            label=f"napoved ({IMENA[izbran]})")
    ax.axhline(sr, color=PALETA[0], lw=0.8, ls=":")
    ax.axhline(0, color="#333333", lw=0.8)
    dni = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]
    ax.set_xticks(np.arange(7) + 0.5, [f"{dni[i]}\n{16 + i}. 11." for i in range(7)])
    ax.set_xticks(np.arange(8), minor=True)
    ax.tick_params(axis="x", which="major", length=0)
    ax.grid(axis="x", which="minor", color="#e5e5e5")
    ax.grid(axis="x", which="major", visible=False)
    ax.set_ylabel("neto [MW]")
    ax.set_title(f"Napoved neto pozicije, teden 47: povprečje {sr:.0f} MW "
                 f"(razpon {sr + q10:.0f} do {sr + q90:.0f})", pad=24)
    ax.legend(ncol=2, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    fig.text(0.99, -0.03, "15-min vrednosti, lokalni čas; + izvoz, − uvoz. Razpon iz testa "
             "na tednih okt–dec 2023–2026.", ha="right", fontsize=7, color="#666666")
    shrani(fig, "b1_napoved_t47_izbrani", FIG_B)

    # --- PREVERJANJE (po zamrznitvi): dejanski dnevi tedna 47, ki so že znani
    m = pd.read_parquet(DATA / "meje.parquet")["sum"]
    m.index = m.index.tz_convert(TZ)
    dej = (-m * 1000)[(m.index >= T47.tz_localize(TZ)) &
                      (m.index < (T47 + pd.Timedelta(days=7)).tz_localize(TZ))]
    dej_d = dej.groupby(dej.index.date).mean()
    dej_d = dej_d[dej.groupby(dej.index.date).count() == 96]
    if len(dej_d):
        t = dn.iloc[:len(dej_d)][["1", "9", "10a", "10b", "12", "14"]].copy()
        t.columns = [IMENA[c] for c in t.columns]
        t.insert(0, "DEJANSKO", dej_d.values)
        print("\nPREVERJANJE – znani dnevi tedna 47 (neto, MW, dnevna povprečja):")
        print(t.round(0).to_string())
