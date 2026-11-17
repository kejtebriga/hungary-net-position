"""
Analiza a): neto pozicija Madžarske – grafi in tabele.

Zagon:  .venv/bin/python src/analiza_a.py 1 2 3 4 5 6   (izbor grafov po številki)

Konvencija predznaka: neto pozicija in meje  + = IZVOZ, − = UVOZ
(Energy-Charts 'cbet' je + = uvoz, zato predznak obrnemo).
Leta so razmejena po lokalnem času (CET/CEST, Europe/Budapest).
Vse vrednosti so povprečna moč v MW (povprečje 15-min vrednosti = povprečje urnih).
"""
import sys
from functools import lru_cache
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

KOREN = Path(__file__).resolve().parent.parent
DATA = KOREN / "data"
FIG = KOREN / "figures"
FIG.mkdir(exist_ok=True)

PALETA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
          "#e87ba4", "#008300", "#6250d6", "#e34948"]
TZ = "Europe/Budapest"
KONEC = pd.Timestamp("2026-11-15 23:45", tz=TZ)  # brez pogleda v prihodnost

plt.rcParams.update({
    "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e5e5e5", "grid.linewidth": 0.6,
    "axes.axisbelow": True, "legend.frameon": False,
    "figure.dpi": 150, "savefig.bbox": "tight",
})


@lru_cache(maxsize=None)
def preberi(ime):
    df = pd.read_parquet(DATA / ime)
    df.index = df.index.tz_convert(TZ)
    return df[df.index <= KONEC]


def oznaka_leta(leta):
    zadnje = max(leta)
    return [f"{l}*" if l == zadnje else str(l) for l in leta]


def shrani(fig, ime):
    for konc in ("pdf", "png"):
        fig.savefig(FIG / f"{ime}.{konc}")
    plt.close(fig)
    print(f"  shranjeno: figures/{ime}.pdf / .png")


# ---------------------------------------------------------------------------
# GRAF 1: letni trend – viri, poraba, neto pozicija
# ---------------------------------------------------------------------------
SKUPINE = {
    "Jedrska (Paks)": ["Nuclear"],
    "Premog (lignit)": ["Fossil brown coal / lignite", "Fossil hard coal"],
    "Plin": ["Fossil gas"],
    "Sonce": ["Solar"],
    "Veter": ["Wind onshore"],
    "Biomasa in odpadki": ["Biomass", "Waste"],
    "Ostalo (voda, olje, drugo)": ["Hydro Run-of-River", "Hydro water reservoir",
                                   "Fossil oil", "Others", "Other renewables",
                                   "Geothermal"],
}


def graf1():
    print("\nGRAF 1 – letni trend")
    p = preberi("proizvodnja.parquet")
    m = preberi("meje.parquet")
    leto = p.index.year

    viri = pd.DataFrame({ime: p[stolpci].sum(axis=1, min_count=1)
                         for ime, stolpci in SKUPINE.items()})
    letno = viri.groupby(leto).mean()
    # sonce: pred sredino 2019 ni podatka -> leta brez polnega podatka pustimo prazna
    pokritost_sonca = p["Solar"].notna().groupby(leto).mean()
    letno.loc[pokritost_sonca < 0.95, "Sonce"] = np.nan

    poraba = p["Load"].groupby(leto).mean()
    neto = (-m["sum"] * 1000).groupby(m.index.year).mean()       # + = izvoz
    proizvodnja = letno.sum(axis=1)

    tab = letno.round(0).copy()
    tab["SKUPAJ proizvodnja"] = proizvodnja.round(0)
    tab["Poraba"] = poraba.round(0)
    tab["Neto (meje, + izvoz)"] = neto.round(0)
    tab["Neto/poraba %"] = (neto / poraba * 100).round(1)
    print("\nLetna povprečja, MW (povprečje vseh 15-min vrednosti v letu; leta po CET)")
    print("2026* = 1. 1. – 14. 11. 2026; Sonce prazno = ni podatka\n")
    print(tab.T.to_string(na_rep="–"))

    # --- izris: (A) 2015–2026 brez sonca + neto pozicija, (B) 2020–2026 s soncem
    brez_sonca = [s for s in SKUPINE if s != "Sonce"]
    izris_virov(letno, poraba, brez_sonca, neto=neto,
                naslov="Proizvodnja brez sonca in poraba (letna povprečja)",
                ime="a1a_letni_trend_brez_sonca",
                opomba="Sonce izpuščeno, ker pred 2020 ni podatka.")
    izris_virov(letno.loc[2020:], poraba.loc[2020:], list(SKUPINE),
                naslov="Proizvodnja po virih in poraba, 2020–2026 (letna povprečja)",
                ime="a1b_letni_trend_s_soncem",
                opomba="Razlika med porabo in proizvodnjo = uvoz.")


def izris_virov(letno, poraba, skupine, naslov, ime, opomba, neto=None):
    leta = letno.index.tolist()
    x = np.arange(len(leta))
    if neto is not None:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.8, 5.6), sharex=True,
                                       gridspec_kw={"height_ratios": [2.3, 1]})
    else:
        fig, ax1 = plt.subplots(figsize=(6.8, 4.0))
    dno = np.zeros(len(leta))
    for ime_vira in skupine:
        i = list(SKUPINE).index(ime_vira)        # barva sledi viru, ne vrstnemu redu
        v = letno[ime_vira].fillna(0).values
        ax1.bar(x, v, bottom=dno, width=0.7 if len(leta) > 8 else 0.6,
                color=PALETA[i], label=ime_vira, edgecolor="white", linewidth=0.8)
        dno += v
    ax1.plot(x, poraba.values, color="#333333", lw=1.4, marker="o", ms=4,
             label="Poraba")
    ax1.set_ylabel("povprečna moč [MW]")
    ax1.set_ylim(0, 5600)
    ax1.legend(ncol=4, fontsize=7.5, loc="lower center",
               bbox_to_anchor=(0.5, 1.03), handlelength=1.2)
    ax1.set_title(naslov, pad=40)
    if neto is not None:
        ax2.bar(x, neto.values, width=0.7, color=PALETA[7])
        ax2.axhline(0, color="#333333", lw=0.8)
        for xi, v in zip(x, neto.values):
            ax2.text(xi, v - 60, f"{v:.0f}", ha="center", va="top",
                     fontsize=7, color="#333333")
        ax2.set_ylim(-1750, 200)
        ax2.set_ylabel("neto [MW]")
        ax2.set_title("Neto pozicija iz trgovanja na mejah (+ izvoz, − uvoz)")
        ax_x = ax2
    else:
        ax_x = ax1
    ax_x.set_xticks(x, oznaka_leta(leta))
    fig.text(0.99, -0.01, f"{opomba}   * 2026: 1. 1. – 14. 11.   "
             "Vir: Energy-Charts", ha="right", fontsize=7, color="#666666")
    shrani(fig, ime)


# ---------------------------------------------------------------------------
# GRAF 2: meje po letih
# ---------------------------------------------------------------------------
MEJE = {"Slovakia": "Slovaška", "Austria": "Avstrija", "Romania": "Romunija",
        "Croatia": "Hrvaška", "Serbia": "Srbija", "Slovenia": "Slovenija",
        "Ukraine": "Ukrajina"}


def graf2():
    print("\nGRAF 2 – meje po letih")
    m = preberi("meje.parquet")
    neto = -m[list(MEJE)] * 1000                       # MW, + = izvoz
    letno = neto.groupby(neto.index.year).mean().rename(columns=MEJE)
    vsota = (-m["sum"] * 1000).groupby(m.index.year).mean()

    tab = letno.round(0).copy()
    tab["SKUPAJ"] = vsota.round(0)
    print("\nNeto trgovanje po mejah, MW (+ izvoz iz HU, − uvoz v HU)")
    print("letna povprečja 15-min vrednosti, leta po CET; prazno = meja še ni "
          "imela trgovanja; 2026* = do 14. 11.\n")
    print(tab.T.to_string(na_rep="–"))

    leta = letno.index.tolist()
    x = np.arange(len(leta))
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    poz = np.zeros(len(leta))
    neg = np.zeros(len(leta))
    for i, ime in enumerate(MEJE.values()):
        v = letno[ime].fillna(0).values
        dno = np.where(v >= 0, poz, neg)
        ax.bar(x, v, bottom=dno, width=0.7, color=PALETA[i], label=ime,
               edgecolor="white", linewidth=0.8)
        poz += np.where(v >= 0, v, 0)
        neg += np.where(v < 0, v, 0)
    ax.plot(x, vsota.values, color="#333333", lw=0, marker="D", ms=5,
            label="Neto skupaj")
    ax.axhline(0, color="#333333", lw=0.8)
    ax.set_xticks(x, oznaka_leta(leta))
    ax.set_ylabel("povprečna moč [MW]")
    ax.text(-0.6, 900, "izvoz ↑", fontsize=8, color="#666666")
    ax.set_ylim(-2300, 1200)
    ax.text(-0.6, -2250, "uvoz ↓", fontsize=8, color="#666666")
    ax.set_title("Neto čezmejno trgovanje po mejah (letna povprečja)", pad=30)
    ax.legend(ncol=8, fontsize=7.5, loc="lower center",
              bbox_to_anchor=(0.5, 1.0), handlelength=1.0, columnspacing=0.9)
    fig.text(0.99, -0.01, "* 2026: 1. 1. – 14. 11.   Vir: Energy-Charts "
             "(trgovanje, ne fizični tokovi)", ha="right", fontsize=7,
             color="#666666")
    shrani(fig, "a2_meje_po_letih")


# ---------------------------------------------------------------------------
# Skupno za grafe 3–6: tri obdobja
# ---------------------------------------------------------------------------
OBDOBJA = {"2015–2026": 2015, "2020–2026": 2020, "2022–2026": 2022}
BARVA_OBD = dict(zip(OBDOBJA, PALETA[:3]))
MESECI = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "avg", "sep",
          "okt", "nov", "dec"]
LETNI_CASI = {"zima (dec–feb)": [12, 1, 2], "pomlad (mar–maj)": [3, 4, 5],
              "poletje (jun–avg)": [6, 7, 8], "jesen (sep–nov)": [9, 10, 11]}


def osnovni_df():
    """15-min tabela: viri (skupine), poraba, neto (iz mej, + izvoz), cena."""
    p = preberi("proizvodnja.parquet")
    m = preberi("meje.parquet")
    df = pd.DataFrame({ime: p[st].sum(axis=1, min_count=1)
                       for ime, st in SKUPINE.items()})
    df["Poraba"] = p["Load"]
    df["Neto"] = (-m["sum"] * 1000).reindex(df.index)
    c = preberi("cena.parquet")["cena"]
    # cena je do jeseni 2025 urna -> vrednost ure prepišemo na njene 4 četrture
    df["Cena"] = c.reindex(df.index.union(c.index)).ffill(limit=3).reindex(df.index)
    return df


def od_leta(df, leto):
    return df[df.index.year >= leto]


# ---------------------------------------------------------------------------
# GRAF 3: po mesecih
# ---------------------------------------------------------------------------
def graf3():
    print("\nGRAF 3 – po mesecih")
    df = osnovni_df()
    poraba, neto = {}, {}
    for obd, l0 in OBDOBJA.items():
        d = od_leta(df, l0)
        poraba[obd] = d["Poraba"].groupby(d.index.month).mean()
        neto[obd] = d["Neto"].groupby(d.index.month).mean()
    poraba, neto = pd.DataFrame(poraba), pd.DataFrame(neto)
    for t in (poraba, neto):
        t.index = MESECI
    print("\nPovprečje po koledarskih mesecih, MW (povprečje 15-min vrednosti; "
          "meseci po CET)")
    print("\nPORABA\n" + poraba.round(0).to_string())
    print("\nNETO POZICIJA (+ izvoz, − uvoz)\n" + neto.round(0).to_string())

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.8, 5.2), sharex=True)
    x = np.arange(12)
    for obd in OBDOBJA:
        a1.plot(x, poraba[obd], color=BARVA_OBD[obd], lw=1.6, marker="o",
                ms=3.5, label=obd)
        a2.plot(x, neto[obd], color=BARVA_OBD[obd], lw=1.6, marker="o",
                ms=3.5, label=obd)
    a1.set_title("Poraba po mesecih")
    a1.set_ylabel("MW")
    a1.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.1))
    a2.set_title("Neto pozicija po mesecih (+ izvoz, − uvoz)")
    a2.set_ylabel("MW")
    a2.axhline(0, color="#333333", lw=0.8)
    a2.set_xticks(x, MESECI)
    fig.text(0.99, -0.01, "Povprečje vseh let v obdobju.  Vir: Energy-Charts",
             ha="right", fontsize=7, color="#666666")
    shrani(fig, "a3a_mesecno_poraba_neto")

    # viri po mesecih – za vsako obdobje (2015–2026 brez sonca)
    for obd, l0 in OBDOBJA.items():
        d = od_leta(df, l0)
        skupine = [s for s in SKUPINE if not (l0 < 2020 and s == "Sonce")]
        mes = d[skupine].groupby(d.index.month).mean()
        mes.index = MESECI
        t = mes.round(0)
        t["Proizv. skupaj"] = mes.sum(axis=1).round(0)
        t["Poraba"] = poraba[obd].round(0)
        t["Neto"] = neto[obd].round(0)
        print(f"\nVIRI PO MESECIH {obd}, MW" +
              (" (brez sonca)" if l0 < 2020 else "") + "\n" +
              t.T.to_string())
    # graf virov po mesecih za 2022–2026 (najboljši podatki)
    d = od_leta(df, 2022)
    mes = d[list(SKUPINE)].groupby(d.index.month).mean()
    fig, ax = plt.subplots(figsize=(6.8, 4.0))
    dno = np.zeros(12)
    for i, ime in enumerate(SKUPINE):
        ax.bar(x, mes[ime].values, bottom=dno, width=0.7, color=PALETA[i],
               label=ime, edgecolor="white", linewidth=0.8)
        dno += mes[ime].values
    ax.plot(x, poraba["2022–2026"].values, color="#333333", lw=1.4,
            marker="o", ms=4, label="Poraba")
    ax.set_xticks(x, MESECI)
    ax.set_ylabel("povprečna moč [MW]")
    ax.set_ylim(0, 6200)
    ax.legend(ncol=4, fontsize=7.5, loc="lower center",
              bbox_to_anchor=(0.5, 1.03), handlelength=1.2)
    ax.set_title("Proizvodnja po virih in poraba po mesecih, 2022–2026", pad=40)
    fig.text(0.99, -0.01, "Razlika med porabo in proizvodnjo = uvoz.  "
             "Vir: Energy-Charts", ha="right", fontsize=7, color="#666666")
    shrani(fig, "a3b_mesecno_viri_2022_2026")


# ---------------------------------------------------------------------------
# GRAF 4: dnevni profil po letnih časih
# ---------------------------------------------------------------------------
def profil(serija):
    """povprečje po 15-min terminih dneva (lokalni čas), indeks = ura (0–23.75)"""
    ura = serija.index.hour + serija.index.minute / 60
    return serija.groupby(ura).mean()


def graf4():
    print("\nGRAF 4 – dnevni profil")
    df = osnovni_df()
    fig, osi = plt.subplots(2, 2, figsize=(6.8, 5.0), sharex=True, sharey=True)
    urna = {}
    for ax, (cas, meseci) in zip(osi.flat, LETNI_CASI.items()):
        for obd, l0 in OBDOBJA.items():
            d = od_leta(df, l0)
            d = d[d.index.month.isin(meseci)]["Neto"]
            pr = profil(d)
            ax.plot(pr.index, pr.values, color=BARVA_OBD[obd], lw=1.4, label=obd)
            urna[(cas, obd)] = d.groupby(d.index.hour).mean()
        ax.axhline(0, color="#333333", lw=0.8)
        ax.set_title(cas)
        ax.set_xticks([0, 6, 12, 18, 24])
    for ax in osi[:, 0]:
        ax.set_ylabel("neto [MW]")
    for ax in osi[1]:
        ax.set_xlabel("ura (lokalni čas)")
    osi[0, 0].legend(ncol=3, loc="lower center", bbox_to_anchor=(1.05, 1.15))
    fig.suptitle("Neto pozicija čez dan po letnih časih (+ izvoz, − uvoz)",
                 y=1.04)
    fig.text(0.99, -0.01, "15-min termini, lokalni čas (CET/CEST).  "
             "Vir: Energy-Charts", ha="right", fontsize=7, color="#666666")
    shrani(fig, "a4a_dnevni_profil_letni_casi")
    t = pd.DataFrame(urna).round(0)
    print("\nNeto pozicija po urah dneva, MW (urno povprečje 15-min vrednosti, "
          "ura = začetek ure, lokalni čas CET/CEST)")
    for cas in LETNI_CASI:
        print(f"\n{cas}\n" + t[cas].T.to_string())

    # jesen (okt–nov) po letih 2020–2026: kako se profil spreminja s soncem
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    leta = range(2020, 2027)
    tab = {}
    for i, leto in enumerate(leta):
        d = df[(df.index.year == leto) & df.index.month.isin([10, 11])]["Neto"]
        pr = profil(d)
        ax.plot(pr.index, pr.values, color=PALETA[i], lw=1.3, label=str(leto))
        tab[leto] = d.groupby(d.index.hour).mean()
    ax.axhline(0, color="#333333", lw=0.8)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xlabel("ura (lokalni čas)")
    ax.set_ylabel("neto [MW]")
    ax.set_title("Neto pozicija čez dan v oktobru in novembru, po letih "
                 "(+ izvoz, − uvoz)", pad=24)
    ax.legend(ncol=7, loc="lower center", bbox_to_anchor=(0.5, 1.0),
              handlelength=1.2)
    fig.text(0.99, -0.06, "2026: okt + 1.–14. nov.  15-min termini, lokalni "
             "čas.  Vir: Energy-Charts", ha="right", fontsize=7, color="#666666")
    shrani(fig, "a4b_profil_okt_nov_po_letih")
    print("\nOKT–NOV po letih, neto po urah, MW (urno povprečje, lokalni čas)\n"
          + pd.DataFrame(tab).round(0).T.to_string())


# ---------------------------------------------------------------------------
# GRAF 5: poraba in temperatura, dnevi v tednu
# ---------------------------------------------------------------------------
def prazniki(leta):
    from dateutil.easter import easter
    dnevi = []
    for l in leta:
        e = pd.Timestamp(easter(l))
        dnevi += [e - pd.Timedelta(days=2), e + pd.Timedelta(days=1),
                  e + pd.Timedelta(days=50)]
        dnevi += [pd.Timestamp(f"{l}-{md}") for md in
                  ("01-01", "03-15", "05-01", "08-20", "10-23", "11-01")]
        dnevi += list(pd.date_range(f"{l}-12-24", f"{l}-12-31"))
    return set(d.date() for d in dnevi)


def prileganje_zalomljeno(T, y):
    """y = a + bh·max(T0−T,0) + bc·max(T−T1,0); T0, T1 z iskanjem po mreži"""
    naj = None
    for T0 in np.arange(8, 20.01, 0.5):
        for T1 in np.arange(max(T0, 16), 28.01, 0.5):
            X = np.column_stack([np.ones_like(T), np.maximum(T0 - T, 0),
                                 np.maximum(T - T1, 0)])
            k, *_ = np.linalg.lstsq(X, y, rcond=None)
            napaka = np.mean(np.abs(X @ k - y))
            if naj is None or napaka < naj[0]:
                naj = (napaka, T0, T1, k)
    return naj


def graf5():
    print("\nGRAF 5 – poraba in temperatura, dnevi v tednu")
    df = osnovni_df()
    v = preberi("vreme.parquet")
    v = v[v["vir"] == "arhiv"]["temperature_2m"]
    dan = pd.DataFrame({"Poraba": df["Poraba"].resample("D").mean(),
                        "T": v.resample("D").mean()}).dropna()
    dan = dan[dan.index < pd.Timestamp("2026-11-14", tz=TZ)]   # le polni dnevi
    pr = prazniki(range(2015, 2027))
    delovni = dan[(dan.index.day_of_week < 5) &
                  ~pd.Series(dan.index.date, index=dan.index).isin(pr)]

    fig, osi = plt.subplots(1, 3, figsize=(6.8, 3.0), sharey=True)
    vrstice = []
    for ax, (obd, l0) in zip(osi, OBDOBJA.items()):
        d = delovni[delovni.index.year >= l0]
        T, y = d["T"].values, d["Poraba"].values
        k_lin = np.polyfit(T, y, 1)
        mae_lin = np.mean(np.abs(np.polyval(k_lin, T) - y))
        mae_z, T0, T1, k = prileganje_zalomljeno(T, y)
        ax.scatter(T, y, s=3, color=BARVA_OBD[obd], alpha=0.35, lw=0)
        tt = np.linspace(T.min(), T.max(), 200)
        ax.plot(tt, np.polyval(k_lin, tt), color="#333333", lw=1.2, ls="--",
                label="ravna črta")
        ax.plot(tt, k[0] + k[1] * np.maximum(T0 - tt, 0) +
                k[2] * np.maximum(tt - T1, 0), color="#333333", lw=1.6,
                label="zalomljena črta")
        ax.set_title(obd)
        ax.set_xlabel("dnevna temperatura [°C]")
        vrstice.append({"obdobje": obd, "dni": len(d),
                        "ravna: MW/°C": round(k_lin[0], 0),
                        "ravna: napaka MW": round(mae_lin, 0),
                        "prelom ogrevanje °C": T0,
                        "ogrevanje: MW na °C hladneje": round(k[1], 0),
                        "prelom hlajenje °C": T1,
                        "hlajenje: MW na °C topleje": round(k[2], 0),
                        "zalomljena: napaka MW": round(mae_z, 0)})
    osi[0].set_ylabel("dnevna poraba [MW]")
    osi[0].legend(loc="lower center", bbox_to_anchor=(1.6, 1.12), ncol=2)
    fig.suptitle("Poraba in temperatura (delovni dnevi, brez praznikov)", y=1.12)
    fig.text(0.99, -0.12, "Točka = en dan. Temperatura: tehtano povprečje 5 "
             "mest.  Vir: Energy-Charts, Open-Meteo", ha="right", fontsize=7,
             color="#666666")
    shrani(fig, "a5a_poraba_temperatura")
    print("\nPoraba vs temperatura: dnevna povprečja (lokalni dan), delovni dnevi "
          "brez praznikov; napaka = povprečno absolutno odstopanje\n")
    print(pd.DataFrame(vrstice).set_index("obdobje").T.to_string())

    # dnevi v tednu
    dnevi = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]
    tab = {}
    for obd, l0 in OBDOBJA.items():
        d = dan[(dan.index.year >= l0) &
                ~pd.Series(dan.index.date, index=dan.index).isin(pr)]
        tab[(obd, "celo leto")] = d["Poraba"].groupby(d.index.day_of_week).mean()
        z = d[d.index.month.isin([10, 11, 12, 1, 2, 3])]
        tab[(obd, "okt–mar")] = z["Poraba"].groupby(z.index.day_of_week).mean()
    tab = pd.DataFrame(tab)
    tab.index = dnevi
    print("\nPoraba po dnevih v tednu, MW (povprečje dnevnih povprečij, "
          "brez praznikov, lokalni čas)\n" + tab.round(0).to_string())
    rel = tab / tab.iloc[:5].mean() * 100 - 100
    print("\nRazlika glede na povprečje pon–pet, %\n" + rel.round(1).to_string())

    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    x = np.arange(7)
    for i, obd in enumerate(OBDOBJA):
        ax.bar(x + (i - 1) * 0.26, tab[(obd, "celo leto")], width=0.24,
               color=BARVA_OBD[obd], label=obd, edgecolor="white", lw=0.8)
    ax.set_xticks(x, dnevi)
    ax.set_ylim(3500, 5400)
    ax.set_ylabel("povprečna poraba [MW]")
    ax.set_title("Poraba po dnevih v tednu (brez praznikov)", pad=22)
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    fig.text(0.99, -0.02, "Os y se ne začne pri 0.  Vir: Energy-Charts",
             ha="right", fontsize=7, color="#666666")
    shrani(fig, "a5b_poraba_dnevi_v_tednu")


# ---------------------------------------------------------------------------
# GRAF 6: capture price
# ---------------------------------------------------------------------------
def graf6():
    print("\nGRAF 6 – capture price")
    df = osnovni_df()
    df = df[df.index.year >= 2020].dropna(subset=["Cena"])
    peak = (df.index.day_of_week < 5) & (df.index.hour >= 8) & (df.index.hour < 20)
    leto = df.index.year
    t = pd.DataFrame({
        "Baseload": df["Cena"].groupby(leto).mean(),
        "Peakload": df.loc[peak, "Cena"].groupby(leto[peak]).mean(),
    })
    for vir in ("Sonce", "Plin", "Jedrska (Paks)"):
        w = df[vir].clip(lower=0)
        t[f"Capture {vir}"] = (w * df["Cena"]).groupby(leto).sum() / \
            w.groupby(leto).sum()
    t["Capture Poraba"] = (df["Poraba"] * df["Cena"]).groupby(leto).sum() / \
        df["Poraba"].groupby(leto).sum()
    t["Sonce / base"] = t["Capture Sonce"] / t["Baseload"]
    t["Plin / base"] = t["Capture Plin"] / t["Baseload"]
    print("\nCene po letih, €/MWh (15-min; pred jesenjo 2025 urna cena "
          "razdeljena na 4 četrture). Peakload = pon–pet 8–20 lokalni čas.")
    print("Capture = s proizvodnjo tehtana cena. 2026 = do 14. 11.\n")
    print(t.round(2).T.to_string())

    # mesečno za 2025: kako se vrednost sonca spreminja čez leto
    d = df[df.index.year == 2025]
    mes = pd.DataFrame({
        "Baseload": d["Cena"].groupby(d.index.month).mean(),
        "Capture Sonce": (d["Sonce"].clip(lower=0) * d["Cena"])
        .groupby(d.index.month).sum() / d["Sonce"].clip(lower=0)
        .groupby(d.index.month).sum()})
    mes["Sonce / base"] = mes["Capture Sonce"] / mes["Baseload"]
    mes.index = MESECI
    print("\n2025 po mesecih, €/MWh\n" + mes.round(2).T.to_string())

    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    leta = t.index.tolist()
    x = np.arange(len(leta))
    serije = [("Baseload", "#333333", "-"), ("Peakload", "#333333", ":"),
              ("Capture Sonce", PALETA[3], "-"), ("Capture Plin", PALETA[2], "-"),
              ("Capture Jedrska (Paks)", PALETA[0], "-")]
    for st, barva, ls in serije:
        ax.plot(x, t[st], color=barva, ls=ls, lw=1.6, marker="o", ms=3.5,
                label=st.replace("Capture ", "vrednost: "))
    ax.set_xticks(x, oznaka_leta(leta))
    ax.set_ylabel("€/MWh")
    ax.set_title("Cena in »vrednost« proizvodnje po virih (capture price)",
                 pad=24)
    ax.legend(ncol=5, loc="lower center", bbox_to_anchor=(0.5, 1.0),
              fontsize=7.5, handlelength=1.6)
    fig.text(0.99, -0.02, "Vrednost = s proizvodnjo tehtana cena.  * 2026: do "
             "14. 11.  Vir: Energy-Charts", ha="right", fontsize=7,
             color="#666666")
    shrani(fig, "a6_capture_price")


GRAFI = {"1": graf1, "2": graf2, "3": graf3, "4": graf4, "5": graf5,
         "6": graf6}

if __name__ == "__main__":
    for st in sys.argv[1:] or GRAFI:
        GRAFI[st]()
