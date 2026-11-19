"""
Angleške različice grafov za angleško poročilo (figures/en/).
Isti podatki in izračuni kot slovenski grafi, le napisi v angleščini – nič se ne računa znova
(napoved in test se preberejo iz shranjenih datotek).

Zagon: .venv/bin/python src/porocilo/grafi_en.py
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

KOREN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KOREN / "src" / "analiza"))
sys.path.insert(0, str(KOREN / "src" / "modeli"))
from analiza_a import (BARVA_OBD, DATA, OBDOBJA, PALETA, SKUPINE, TZ, osnovni_df,
                       prazniki, preberi, prileganje_zalomljeno, profil, shrani)

FIG_EN = KOREN / "figures" / "en"
OPOMBA = dict(ha="right", fontsize=9.5, color="#666666")
VIRI_EN = {"Jedrska (Paks)": "Nuclear (Paks)", "Premog (lignit)": "Coal (lignite)",
           "Plin": "Gas", "Sonce": "Solar", "Veter": "Wind",
           "Biomasa in odpadki": "Biomass and waste",
           "Ostalo (voda, olje, drugo)": "Other (hydro, oil, other)"}
MODELI_EN = {"1": "naive (same as last week)", "2": "seasonal (same as last year)",
             "3a": "mean of 2 weeks", "3b": "mean of 4 weeks", "3c": "2 weeks + level of 3 days",
             "4": "one driver: temperature", "5": "one driver: solar", "6": "one driver: Paks",
             "7": "one driver: gas", "8": "residual load", "9": "linear regression",
             "10a": "formula (gas 2 weeks)", "10b": "formula (gas 3 days)",
             "11": "similar days", "12": "neural network (daily)",
             "12p": "neural network (profile 96)", "13": "short+long (10a,10b)",
             "14": "combination (9,10b,11)"}
SKUPINA = {"1": 0, "2": 0, "3a": 0, "3b": 0, "3c": 0, "4": 1, "5": 1, "6": 1, "7": 1,
           "8": 2, "9": 2, "10a": 2, "10b": 2, "11": 2, "12": 2, "12p": 2, "13": 3, "14": 3}
SKUPINE_EN = ["simple", "one driver", "all drivers", "combinations"]
IZBRAN = "14"


def graf_viri(df):
    d = df[df.index.year >= 2020]
    letno = d[list(SKUPINE)].groupby(d.index.year).mean()
    poraba = d["Poraba"].groupby(d.index.year).mean()
    leta = letno.index.tolist()
    x = np.arange(len(leta))
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    dno = np.zeros(len(leta))
    for i, ime in enumerate(SKUPINE):
        v = letno[ime].fillna(0).values
        ax.bar(x, v, bottom=dno, width=0.6, color=PALETA[i], label=VIRI_EN[ime],
               edgecolor="white", linewidth=0.8)
        dno += v
    ax.plot(x, poraba.values, color="#333333", lw=1.4, marker="o", ms=4, label="Load")
    ax.set_ylabel("average power [MW]")
    ax.set_ylim(0, 5600)
    ax.set_xticks(x, [f"{l}*" if l == max(leta) else str(l) for l in leta])
    ax.legend(ncol=4, fontsize=7.5, loc="lower center", bbox_to_anchor=(0.5, 1.03),
              handlelength=1.2)
    fig.text(0.99, -0.01, "Gap between load and generation = imports.   * 2026: 1 Jan – 15 Nov."
             "   Source: Energy-Charts", **OPOMBA)
    shrani(fig, "a1b_generation_load_2020_2026", FIG_EN)


def graf_temperatura(df):
    v = preberi("vreme.parquet")
    v = v[v["vir"] == "arhiv"]["temperature_2m"]
    dan = pd.DataFrame({"Poraba": df["Poraba"].resample("D").mean(),
                        "T": v.resample("D").mean()}).dropna()
    dan = dan[dan.index < pd.Timestamp("2026-11-14", tz=TZ)]
    pr = prazniki(range(2015, 2027))
    delovni = dan[(dan.index.day_of_week < 5) &
                  ~pd.Series(dan.index.date, index=dan.index).isin(pr)]
    fig, osi = plt.subplots(1, 3, figsize=(6.8, 3.0), sharey=True)
    for ax, (obd, l0) in zip(osi, OBDOBJA.items()):
        d = delovni[delovni.index.year >= l0]
        T, y = d["T"].values, d["Poraba"].values
        k_lin = np.polyfit(T, y, 1)
        _, T0, T1, k = prileganje_zalomljeno(T, y)
        ax.scatter(T, y, s=3, color=BARVA_OBD[obd], alpha=0.35, lw=0)
        tt = np.linspace(T.min(), T.max(), 200)
        ax.plot(tt, np.polyval(k_lin, tt), color="#333333", lw=1.2, ls="--",
                label="straight line")
        ax.plot(tt, k[0] + k[1] * np.maximum(T0 - tt, 0) + k[2] * np.maximum(tt - T1, 0),
                color="#333333", lw=1.6, label="piecewise line")
        ax.set_title(obd)
        ax.set_xlabel("daily temperature [°C]")
    osi[0].set_ylabel("daily load [MW]")
    osi[0].legend(loc="lower center", bbox_to_anchor=(1.6, 1.12), ncol=2)
    fig.text(0.99, -0.12, "Each dot = one day. Temperature: weighted average of 5 cities.  "
             "Sources: Energy-Charts, Open-Meteo", **OPOMBA)
    shrani(fig, "a5a_load_temperature", FIG_EN)


def graf_profil(df):
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    for i, leto in enumerate(range(2020, 2027)):
        d = df[(df.index.year == leto) & df.index.month.isin([10, 11])]["Neto"]
        pr = profil(d)
        ax.plot(pr.index, pr.values, color=PALETA[i], lw=1.3, label=str(leto))
    ax.axhline(0, color="#333333", lw=0.8)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xlabel("hour (local time)")
    ax.set_ylabel("net position [MW]")
    ax.legend(ncol=7, loc="lower center", bbox_to_anchor=(0.5, 1.0), handlelength=1.2)
    fig.text(0.99, -0.06, "2026: Oct + 1–15 Nov.  15-min values, local time.  "
             "Source: Energy-Charts", **OPOMBA)
    shrani(fig, "a4b_daily_profile_oct_nov", FIG_EN)


def graf_modeli():
    R = pd.read_parquet(DATA / "b_modeli_test.parquet")
    vsi = R.groupby("model")["napaka_teden"].apply(lambda e: e.abs().mean())
    rel = (vsi / vsi["1"]).sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    y = np.arange(len(rel))
    for s in range(4):
        m = [i for i in rel.index if SKUPINA[i] == s]
        ax.barh([list(rel.index).index(i) for i in m], rel[m], color=PALETA[s],
                height=0.7, label=SKUPINE_EN[s])
    ax.set_yticks(y, [f"{i} {MODELI_EN[i]}" for i in rel.index], fontsize=7.5)
    for oznaka, model in zip(ax.get_yticklabels(), rel.index):
        if model == IZBRAN:
            oznaka.set_fontweight("bold")
    ax.axvline(1, color="#333333", lw=1, ls="--")
    for yi, v in zip(y, rel.values):
        ax.text(v + 0.01, yi, f"{v:.2f}", va="center", fontsize=7)
    ax.set_xlabel("weekly error relative to the naive model (lower = better)")
    ax.set_xlim(0, 1.5)
    ax.legend(ncol=4, loc="lower center", bbox_to_anchor=(0.45, 1.0), fontsize=7.5)
    ax.grid(axis="y", visible=False)
    shrani(fig, "b3_model_comparison", FIG_EN)


def graf_napoved():
    q = pd.read_parquet(DATA / "b_napovedi_t47_15min.parquet")[IZBRAN]
    R = pd.read_parquet(DATA / "b_modeli_test.parquet")
    e15 = pd.read_parquet(DATA / "b_modeli_napake15.parquet")
    jes15 = e15[e15["teden"].dt.month.isin([10, 11, 12])]
    pas = jes15.groupby(jes15.index.hour)[IZBRAN].quantile([0.1, 0.9]).unstack()
    spodaj = q.values + pas[0.1].reindex(q.index.hour).values
    zgoraj = q.values + pas[0.9].reindex(q.index.hour).values
    sr = q.mean()
    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    x = np.arange(len(q)) / 96
    ax.fill_between(x, spodaj, zgoraj, color=PALETA[0], alpha=0.18, lw=0,
                    label="range (10–90 %)")
    ax.plot(x, q.values, color=PALETA[0], lw=1.4, label="forecast (combination of models 9, 10b, 11)")
    ax.axhline(sr, color=PALETA[0], lw=0.8, ls=":")
    ax.axhline(0, color="#333333", lw=0.8)
    dni = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    ax.set_xticks(np.arange(7) + 0.5, [f"{dni[i]}\n{16 + i} Nov" for i in range(7)])
    ax.set_xticks(np.arange(8), minor=True)
    ax.tick_params(axis="x", which="major", length=0)
    ax.grid(axis="x", which="minor", color="#e5e5e5")
    ax.grid(axis="x", which="major", visible=False)
    ax.set_ylabel("net position [MW]")
    ax.legend(ncol=2, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    fig.text(0.99, -0.09, "15-min values, local time; + export, − import. Range from the test "
             "on Oct–Dec weeks 2023–2026.", **OPOMBA)
    shrani(fig, "b1_forecast_week47", FIG_EN)


if __name__ == "__main__":
    df = osnovni_df()
    graf_viri(df)
    graf_temperatura(df)
    graf_profil(df)
    graf_modeli()
    graf_napoved()
