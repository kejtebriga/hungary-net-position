"""
c) Ali bo povprečna dan-vnaprej cena v tednu 47 VIŠJA ali NIŽJA od tedna 45 (290,98 €/MWh)?

Logika (merit order): cena ≈ cena plina × »faktor«; faktor je večji, ko je preostale
porabe veliko (mraz, malo sonca, manj Paksa → dražje elektrarne in več uvoza) in
manjši, ko v regiji piha (veter v Nemčiji → poceni elektrika pri sosedih).

1. Tabela dejavnikov: teden 45 → teden 46 → teden 47 (napoved)
2. Graf merit order: faktor (cena/TTF) proti preostali porabi
3. Cenovni modeli, testirani na tednih od 2024: koliko krat pravilno ugotovijo SMER
   (teden W proti tednu W−2 – enako kot t47 proti t45)
4. Odločitev za teden 47 (+ base/peak)

Brez pogleda v prihodnost: le podatki do ned 15. 11. 2026 23:45; TTF zadnji znani
(pet 13. 11.); vreme in veter DE: napoved s 14. 11. V testu izmerjeno vreme/veter.
Zagon: .venv/bin/python src/modeli/cena_c.py
"""
import sys
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from modeli_b import (D, T47, Mreze, dnevna_tabela, obcutljivost,
                      po_tipu)
from napoved_b import (DATA, KOREN, TZ, napovej_teden, oceni_parametre,
                       pripravi_podatke)
from analiza_a import KONEC, PALETA, preberi, shrani

warnings.filterwarnings("ignore")
FIG_C = KOREN / "figures" / "c"
T45, T46 = T47 - 14 * D, T47 - 7 * D
CENA_T45 = 290.98
# veter DE je v podatkih od 2023 → test cen od 2024 (vsaj 1 leto za učenje)
TEDNI_TEST = pd.date_range("2024-01-01", "2026-11-09", freq="W-MON")
VHODI_C = ["sob", "ned", "ttf", "pre_fc", "veter_de", "cena_lw"]


# ---------------------------------------------------------------------------
# 1. PODATKI
# ---------------------------------------------------------------------------
def podatki_c():
    df, vreme, tipi = pripravi_podatke()
    dan = dnevna_tabela(df, vreme, tipi)
    c = preberi("cena.parquet")["cena"]
    c15 = c.resample("15min").ffill(limit=3)            # urne cene → 4 četrture
    dan["cena"] = _dnevno(c15)
    peak = (c15.index.day_of_week < 5) & (c15.index.hour >= 8) & (c15.index.hour < 20)
    dan["cena_peak"] = _dnevno(c15[peak])

    # TTF: zadnja znana zaključna cena (investing.com, MM/DD/YYYY)
    t = pd.read_csv(DATA / "Dutch TTF Natural Gas Futures Historical Data.csv")
    ttf = pd.Series(t["Price"].values, index=pd.to_datetime(t["Date"], format="%m/%d/%Y"))
    ttf = ttf.sort_index()
    dan["ttf_dnevni"] = ttf.reindex(dan.index)
    dan["ttf_znan"] = ttf.reindex(dan.index).ffill()    # zadnja znana do tega dne

    # veter v Nemčiji (4 točke na severu, 100 m): arhiv + napoved s 14. 11.
    v = pd.read_parquet(DATA / "veter_de.parquet")["veter_100m"]
    v.index = v.index.tz_convert(TZ)
    dan["veter_de"] = _dnevno(v)

    sos = preberi("cene_sosedi.parquet")
    for s in ("AT", "SK", "RO", "HR", "SI", "DE-LU"):
        dan[f"cena_{s}"] = _dnevno(sos[s])
    return df, vreme, tipi, dan


def _dnevno(s):
    d = s.resample("D").mean()
    d.index = d.index.tz_localize(None)
    return d


def vhodi_c(dan, W):
    """vhodi za cenovne modele za 7 dni tedna W – znani v nedeljo pred W"""
    t = dan.loc[W:W + 6 * D].copy()
    tip = t["tip"]
    t["sob"] = (tip == "sob").astype(float)
    t["ned"] = (tip == "ned").astype(float)
    t["ttf"] = dan.loc[:W - D, "ttf_znan"].iloc[-1]                  # zadnji znani TTF
    t["cena_lw"] = dan.loc[W - 7 * D:W - D, "cena"].values
    # napoved preostale porabe (enako kot model 8 pri b): 2 tedna + temperatura,
    # sonce, Paks iz zadnjih 3 dni
    k_por = obcutljivost(dan, W, "Poraba", ["HDD", "CDD"])
    k_son = obcutljivost(dan, W, "Sonce", ["sevanje"])[0]
    baza = lambda c: po_tipu(dan, W, c).reindex(tip).values
    d_por = (t[["HDD", "CDD"]].values - np.column_stack([baza("HDD"), baza("CDD")])) @ k_por
    d_son = k_son * (t["sevanje"].values - baza("sevanje"))
    paks3 = dan.loc[W - 3 * D:W - D, "Paks"].mean()
    t["pre_fc"] = baza("Preostala") + d_por - d_son - (paks3 - baza("Paks"))
    t["izvor"] = W
    return t


# ---------------------------------------------------------------------------
# 2. CENOVNI MODELI
# ---------------------------------------------------------------------------
def ucni(Fc, W):
    u = Fc[(Fc["izvor"] < W) & (Fc["izvor"] >= W - pd.DateOffset(years=3))]
    return u.dropna(subset=VHODI_C + ["cena"])


def napovej_ceno(Fc, W, mreze):
    t = Fc[Fc["izvor"] == W]
    u = ucni(Fc, W)
    out = {"C1 naivni (kot prejšnji teden)": t["cena_lw"].values}
    # C2 linearna regresija na ceno
    X = np.column_stack([np.ones(len(u)), u[VHODI_C].values])
    k, *_ = np.linalg.lstsq(X, u["cena"].values, rcond=None)
    out["C2 regresija"] = np.column_stack([np.ones(len(t)), t[VHODI_C].values]) @ k
    # C3 merit order: faktor = cena/TTF iz preostale porabe in vetra v DE
    vh = ["sob", "ned", "pre_fc", "veter_de"]
    X = np.column_stack([np.ones(len(u)), u[vh].values])
    k3, *_ = np.linalg.lstsq(X, (u["cena"] / u["ttf"]).values, rcond=None)
    out["C3 merit order (TTF × faktor)"] = \
        t["ttf"].values * (np.column_stack([np.ones(len(t)), t[vh].values]) @ k3)
    # C4 nevronska mreža (isti vhodi kot C2)
    out["C4 nevronska mreža"] = mreze.napovej(t[VHODI_C].values).ravel()
    return pd.DataFrame(out, index=t.index), k3


# ---------------------------------------------------------------------------
# 3. GLAVNI DEL
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    pd.set_option("display.width", 220)
    df, vreme, tipi, dan = podatki_c()
    izvori = pd.date_range("2019-12-30", T47, freq="W-MON")
    Fc = pd.concat([vhodi_c(dan, W) for W in izvori])
    tedenska = dan["cena"].resample("W-MON", label="left", closed="left").mean()
    print(f"Kontrola: povprečna cena tedna 45 = {dan.loc[T45:T45 + 6 * D, 'cena'].mean():.2f}"
          f" €/MWh (naloga: {CENA_T45})")

    # --- test na 202 tednih: napaka in pravilna smer (W proti W−2)
    vr, mreze = [], None
    for i, W in enumerate(TEDNI_TEST):
        if i % 4 == 0:
            u = ucni(Fc, W)
            mreze = Mreze(5).nauci(u[VHODI_C].values, u[["cena"]].values)
        nap, _ = napovej_ceno(Fc, W, mreze)
        dej = dan.loc[W:W + 6 * D, "cena"].mean()
        ref = tedenska.get(W - 14 * D)                   # cena 2 tedna prej (kot t45)
        for m in nap:
            p = nap[m].mean()
            vr.append({"teden": W, "model": m, "dejansko": dej, "napoved": p,
                       "napaka": abs(dej - p),
                       "smer_ok": np.sign(p - ref) == np.sign(dej - ref)})
    R = pd.DataFrame(vr)
    R.to_parquet(DATA / "c_modeli_test.parquet")
    print(f"\nTEST cenovnih modelov, {len(TEDNI_TEST)} tednov (1. 1. 2024 – 15. 11. 2026); "
          "smer = ali je teden višji/nižji od tedna 2 prej")
    g = R.groupby("model")
    jesen = R[R["teden"].dt.month.isin([10, 11, 12])].groupby("model")
    print(pd.DataFrame({"napaka tedna €/MWh": g["napaka"].mean(),
                        "pravilna smer %": g["smer_ok"].mean() * 100,
                        "okt–dec: napaka": jesen["napaka"].mean(),
                        "okt–dec: smer %": jesen["smer_ok"].mean() * 100})
          .round(1).to_string())

    # --- napoved tedna 47
    u = ucni(Fc, T47)
    mreze = Mreze(5).nauci(u[VHODI_C].values, u[["cena"]].values)
    nap47, k3 = napovej_ceno(Fc, T47, mreze)
    print("\nMerit order (C3) za teden 47: faktor = cena/TTF = "
          f"{k3[0]:.2f} {k3[3]:+.5f}·preostala {k3[4]:+.4f}·veter_DE "
          f"{k3[1]:+.2f}·sob {k3[2]:+.2f}·ned")
    t = nap47.copy()
    t.index = [d.strftime("%a %d.%m.") for d in t.index]
    t.loc["TEDEN 47 (base)"] = nap47.mean()
    print("\nNAPOVED CENE TEDNA 47, €/MWh (dnevna povprečja)")
    print(t.T.round(1).to_string())
    nap47.to_parquet(DATA / "c_napoved_t47.parquet")

    # --- tabela dejavnikov t45 → t46 → t47
    t47 = Fc[Fc["izvor"] == T47]
    n10 = napovej_teden(df, vreme, tipi, T47.tz_localize(TZ),
                        oceni_parametre(df, vreme, tipi, T47.tz_localize(TZ), 3), plin="3d")
    def teden(W, c):
        return dan.loc[W:W + 6 * D, c].mean()
    vrst = {
        "cena HU base [€/MWh]": (teden(T45, "cena"), teden(T46, "cena"), nap47.mean().mean()),
        "cena HU peak [€/MWh]": (teden(T45, "cena_peak"), teden(T46, "cena_peak"), np.nan),
        "TTF plin [€/MWh]": (teden(T45, "ttf_dnevni"), teden(T46, "ttf_dnevni"), t47["ttf"].iloc[0]),
        "temperatura HU [°C]": (teden(T45, "T"), teden(T46, "T"), t47["T"].mean()),
        "poraba HU [MW]": (teden(T45, "Poraba"), teden(T46, "Poraba"), n10["Poraba"].mean()),
        "sonce HU [MW]": (teden(T45, "Sonce"), teden(T46, "Sonce"), n10["Sonce"].mean()),
        "Paks [MW]": (teden(T45, "Paks"), teden(T46, "Paks"), n10["Paks"].mean()),
        "preostala poraba HU [MW]": (teden(T45, "Preostala"), teden(T46, "Preostala"),
                                     t47["pre_fc"].mean()),
        "veter S Nemčija [km/h]": (teden(T45, "veter_de"), teden(T46, "veter_de"),
                                   t47["veter_de"].mean()),
        "neto HU [MW] (+ izvoz)": (teden(T45, "Neto"), teden(T46, "Neto"), np.nan),
    }
    for s in ("AT", "SK", "RO", "DE-LU"):
        vrst[f"cena {s} [€/MWh]"] = (teden(T45, f"cena_{s}"), teden(T46, f"cena_{s}"), np.nan)
    D_tab = pd.DataFrame(vrst, index=["teden 45", "teden 46", "teden 47 (napoved)"]).T
    print("\nDEJAVNIKI (tedenska povprečja; t47 = napoved / zadnje znano)")
    print(D_tab.round(1).to_string())
    D_tab.to_csv(DATA / "c_dejavniki.csv")

    # --- GRAF c1: merit order – faktor cena/TTF proti preostali porabi (zadnje leto)
    z = dan.loc[KONEC.tz_localize(None).normalize() - pd.DateOffset(years=1):T47 - D]
    z = z.dropna(subset=["cena", "ttf_znan", "Preostala"])
    faktor = z["cena"] / z["ttf_znan"]
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    ax.scatter(z["Preostala"], faktor, s=9, color=PALETA[0], alpha=0.45, lw=0,
               label="dan (zadnjih 12 mesecev)")
    razredi = pd.cut(z["Preostala"], np.arange(1500, 6001, 250))
    sr = faktor.groupby(razredi).median()
    ax.plot([i.mid for i in sr.index], sr.values, color="#333333", lw=1.6,
            label="mediana")
    for W, ime, barva in ((T45, "teden 45", PALETA[1]), (T46, "teden 46", PALETA[2])):
        x = teden(W, "Preostala")
        y = teden(W, "cena") / teden(W, "ttf_znan")
        ax.scatter([x], [y], s=60, color=barva, edgecolor="white", lw=1.2, zorder=5,
                   label=f"{ime} (dejansko)")
    x47 = t47["pre_fc"].mean()
    ax.axvline(x47, color=PALETA[3], lw=1.4, ls="--", label="teden 47: napoved preostale")
    ax.set_xlabel("preostala poraba HU = poraba − sonce − veter − Paks [MW]")
    ax.set_ylabel("cena / cena plina TTF")
    ax.set_title("Merit order: več preostale porabe → dražja elektrika", pad=40)
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.02), fontsize=7.5)
    fig.text(0.99, -0.03, "Dnevna povprečja, lokalni čas. TTF = zadnja znana cena plina. "
             "Vir: Energy-Charts, investing.com", ha="right", fontsize=7, color="#666666")
    shrani(fig, "c1_merit_order", FIG_C)

    # --- GRAF c2: dnevne cene t45, t46 in napoved t47
    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    x = np.arange(7)
    for j, (W, ime, barva) in enumerate(((T45, "teden 45", PALETA[1]),
                                         (T46, "teden 46", PALETA[2]))):
        ax.bar(x + (j - 1) * 0.27, dan.loc[W:W + 6 * D, "cena"].values, width=0.25,
               color=barva, label=ime, edgecolor="white", lw=0.8)
    izbran = "C2 regresija"                     # najmanjša napaka v testu
    ax.bar(x + 0.27, nap47[izbran].values, width=0.25, color=PALETA[0],
           label="teden 47 (napoved C2)", edgecolor="white", lw=0.8)
    ax.axhline(CENA_T45, color="#333333", lw=1, ls="--")
    ax.text(6.6, CENA_T45 + 6, f"povp. t45 = {CENA_T45}", ha="right", fontsize=7.5)
    ax.set_xticks(x, ["pon", "tor", "sre", "čet", "pet", "sob", "ned"])
    ax.set_ylabel("dnevna povprečna cena [€/MWh]")
    ax.set_title("Dan-vnaprej cena HU: teden 45, 46 in napoved 47", pad=22)
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    shrani(fig, "c2_cene_po_dnevih", FIG_C)
