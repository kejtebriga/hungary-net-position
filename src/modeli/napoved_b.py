"""
b) Napoved neto pozicije Madžarske za teden 47 (pon 16. – ned 22. 11. 2026).

IDEJA (po kosih):  neto = proizvodnja − poraba   (formula iz naloge)
Vsak kos napovemo posebej, izhodišče sta zadnja dva tedna pred napovedjo:

  poraba  = profil zadnjih 2 tednov (ločeno delovni dan / sobota / nedelja)
            + popravek za temperaturo (ogrevanje: MW na °C pod pragom)
  Paks    = povprečje zadnjih 3 dni (jedrska dela enakomerno)
  sonce   = profil zadnjih 2 tednov × (napovedano sevanje / sevanje zadnjih 2 tednov)
  veter, premog, biomasa, ostalo = profil zadnjih 2 tednov
  plin    = profil zadnjih 2 tednov + delež × sprememba »preostale porabe«
            (preostala poraba = kar morajo pokriti plin in uvoz; merit order)
  neto    = vsota proizvodnje − poraba

TEST (backtest): za vsak teden od 2023 naprej se »postavimo« v nedeljo pred njim,
napovemo z enakim postopkom in primerjamo z dejanskim. Primerjamo z dvema
preprostima napovedma: »enako kot prejšnji teden« in »povprečje zadnjih 2 tednov«.

Vse v lokalnem času (Europe/Budapest), 15-min vrednosti, MW, + = izvoz.
Brez pogleda v prihodnost: uporabimo le podatke do ned 15. 11. 2026 23:45.
Zagon: .venv/bin/python src/modeli/napoved_b.py
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# skupne funkcije (branje podatkov, prazniki, zalomljena črta) so v analiza_a.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analiza"))
from analiza_a import (DATA, KONEC, KOREN, PALETA, SKUPINE, TZ, osnovni_df, preberi,
                       prazniki, prileganje_zalomljeno, shrani)

FIG_B = KOREN / "figures" / "b"
T47 = pd.Timestamp("2026-11-16", tz=TZ)          # ponedeljek tedna 47
DNI = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]


# ---------------------------------------------------------------------------
# 1. PODATKI
# ---------------------------------------------------------------------------
def pripravi_podatke():
    df = osnovni_df()                                 # že odrezano pri KONEC
    df = df[["Jedrska (Paks)", "Premog (lignit)", "Plin", "Sonce", "Veter",
             "Biomasa in odpadki", "Ostalo (voda, olje, drugo)", "Poraba", "Neto"]]
    df = df.rename(columns={"Jedrska (Paks)": "Paks", "Premog (lignit)": "Premog",
                            "Biomasa in odpadki": "Biomasa",
                            "Ostalo (voda, olje, drugo)": "Ostalo"})
    df["Sonce"] = df["Sonce"].fillna(0)
    # majhna razlika med mejami in (proizvodnja − poraba) – ohranimo jo kot svoj kos
    df["Uskladitev"] = df["Neto"] - (df[["Paks", "Premog", "Plin", "Sonce", "Veter",
                                         "Biomasa", "Ostalo"]].sum(axis=1) - df["Poraba"])

    # vreme: dnevna temperatura in dnevno sončno sevanje (lokalni dan)
    v = preberi("vreme.parquet")   # do 15. 11. izmerjeno/analiza; za t47 napoved s 14. 11.
    v_vse = pd.read_parquet(DATA / "vreme.parquet")
    v_vse.index = v_vse.index.tz_convert(TZ)
    # za teden 47 vzamemo napoved, ki je bila prenesena 14. 11. (pred napovedjo)
    v = pd.concat([v, v_vse[(v_vse.index > KONEC) &
                            (v_vse.index < T47 + pd.DateOffset(days=7))]])
    vreme = pd.DataFrame({"T": v["temperature_2m"].resample("D").mean(),
                          "sevanje": v["shortwave_radiation"].resample("D").sum()})
    vreme.index = vreme.index.date                  # indeks = koledarski dan

    # tip dneva: delovni / sob / ned ; prazniki štejejo kot nedelja
    pr = prazniki(range(2015, 2027))
    def tip(ts):
        if ts.date() in pr or ts.day_of_week == 6:
            return "ned"
        return "sob" if ts.day_of_week == 5 else "delovni"
    dnevi = pd.date_range("2015-01-01", "2026-11-22", freq="D")
    tipi = pd.Series([tip(d) for d in dnevi], index=dnevi.date)
    return df, vreme, tipi


def dodaj_kljuce(d, tipi):
    """doda stolpca 'tip' (delovni/sob/ned) in 'termin' (ura:minuta)"""
    d = d.copy()
    d["tip"] = tipi.reindex(d.index.date).values
    d["termin"] = d.index.strftime("%H:%M")
    return d


# ---------------------------------------------------------------------------
# 2. PARAMETRI (ocenimo iz preteklih let)
# ---------------------------------------------------------------------------
def oceni_parametre(df, vreme, tipi, do, let):
    """
    do  = do katerega trenutka smemo gledati,  let = koliko let nazaj (None = vse)
    Vrne: prag ogrevanja T0, MW/°C za ogrevanje, prag in MW/°C za hlajenje,
          delež plina (koliko dodatne preostale porabe pokrije plin).
    """
    od = pd.Timestamp("2015-01-01", tz=TZ) if let is None else do - pd.DateOffset(years=let)
    d = df[(df.index >= od) & (df.index < do)]
    dan = d.resample("D").mean()
    dan.index = dan.index.date
    dan = dan.join(vreme).dropna(subset=["Poraba", "T"])
    delovni = dan[tipi.reindex(dan.index).values == "delovni"]
    _, T0, T1, k = prileganje_zalomljeno(delovni["T"].values, delovni["Poraba"].values)

    # delež plina: vsak dan primerjamo z istim dnem teden prej (izloči dan v tednu)
    dan = dan[[x.year >= 2020 for x in dan.index]]   # pred 2020 ni sonca v podatkih
    preostala = dan["Poraba"] - dan["Sonce"] - dan["Veter"] - dan["Paks"]
    d_pre = (preostala - preostala.shift(7)).dropna()
    d_plin = (dan["Plin"] - dan["Plin"].shift(7)).reindex(d_pre.index).dropna()
    d_pre = d_pre.reindex(d_plin.index)
    delez = float((d_pre * d_plin).sum() / (d_pre ** 2).sum())   # premica skozi 0
    return {"T0": T0, "ogrev": k[1], "T1": T1, "hlaj": k[2], "delez_plina": delez}


# ---------------------------------------------------------------------------
# 3. NAPOVED ZA EN TEDEN
# ---------------------------------------------------------------------------
def napovej_teden(df, vreme, tipi, ponedeljek, par, plin="2t"):
    """Napoved po kosih za 7 dni od 'ponedeljek'; uporabi le podatke pred njim.
    plin = "2t": raven plina iz zadnjih 2 tednov;  "3d": oblika iz 2 tednov,
    raven iz zadnjih 3 dni (ujame nenadne spremembe, npr. padec plina 13. 11.)."""
    zac_baze = ponedeljek - pd.DateOffset(days=14)
    baza = dodaj_kljuce(df[(df.index >= zac_baze) & (df.index < ponedeljek)], tipi)
    cilj = pd.date_range(ponedeljek, ponedeljek + pd.DateOffset(days=7),
                         freq="15min", inclusive="left")
    n = dodaj_kljuce(pd.DataFrame(index=cilj), tipi)

    # profili zadnjih 2 tednov: po tipu dneva + terminu, ali samo po terminu
    po_tipu = baza.groupby(["tip", "termin"]).mean(numeric_only=True)
    po_terminu = baza.groupby("termin").mean(numeric_only=True)
    def profil(kos, loci_tip=True):
        if loci_tip:
            kljuc = pd.MultiIndex.from_arrays([n["tip"], n["termin"]])
            return po_tipu[kos].reindex(kljuc).values
        return po_terminu[kos].reindex(n["termin"]).values

    # vreme: dnevne vrednosti za ciljni teden in za bazna 2 tedna
    dan_cilj = vreme.reindex(n.index.date)
    vreme_baze = vreme.reindex(sorted(set(baza.index.date)))

    # --- PORABA: profil + popravek za temperaturo (zalomljena črta)
    def stopinje(T):
        return par["ogrev"] * np.maximum(par["T0"] - T, 0) + \
               par["hlaj"] * np.maximum(T - par["T1"], 0)
    popravek_T = stopinje(dan_cilj["T"].values) - stopinje(vreme_baze["T"]).mean()
    n["Poraba"] = profil("Poraba") + popravek_T

    # --- PAKS: povprečje zadnjih 3 dni
    n["Paks"] = baza["Paks"].iloc[-3 * 96:].mean()

    # --- SONCE: profil × razmerje sevanja
    razmerje = dan_cilj["sevanje"].values / vreme_baze["sevanje"].mean()
    n["Sonce"] = profil("Sonce", loci_tip=False) * razmerje

    # --- STABILNI KOSI: kot zadnja 2 tedna
    n["Veter"] = profil("Veter", loci_tip=False)
    for kos in ("Premog", "Biomasa", "Ostalo", "Uskladitev"):
        n[kos] = profil(kos)

    # --- PLIN: profil + delež spremembe preostale porabe
    sprememba = (n["Poraba"] - profil("Poraba")) \
        - (n["Sonce"] - profil("Sonce", loci_tip=False)) \
        - (n["Paks"] - baza["Paks"].mean())
    plin_osnova = profil("Plin")
    if plin == "3d":
        plin_osnova = plin_osnova + (baza["Plin"].iloc[-3 * 96:].mean() - baza["Plin"].mean())
    n["Plin"] = np.maximum(plin_osnova + par["delez_plina"] * sprememba, 0)

    # --- NETO
    proizvodnja = n[["Paks", "Premog", "Plin", "Sonce", "Veter", "Biomasa",
                     "Ostalo"]].sum(axis=1)
    n["Neto"] = proizvodnja - n["Poraba"] + n["Uskladitev"]

    # primerjalni napovedi
    # »enako kot prejšnji teden«: isti dan v tednu, ista ura:minuta
    prejsnji = baza[baza.index >= ponedeljek - pd.DateOffset(days=7)]
    po_dnevu = prejsnji.groupby([prejsnji.index.day_of_week, "termin"])["Neto"].mean()
    n["Naivna"] = po_dnevu.reindex(
        pd.MultiIndex.from_arrays([n.index.day_of_week, n["termin"]])).values
    n["Povp2"] = profil("Neto")
    return n


# ---------------------------------------------------------------------------
# 4. TEST NA VSEH TEDNIH
# ---------------------------------------------------------------------------
def backtest(df, vreme, tipi, let):
    vrstice, napake15 = [], []
    par_leto = {}
    tedni = pd.date_range("2023-01-02", "2026-11-09", freq="W-MON", tz=TZ)
    for pon in tedni:
        # parametre ocenimo enkrat na leto, s podatki do 1. januarja tega leta
        if pon.year not in par_leto:
            par_leto[pon.year] = oceni_parametre(
                df, vreme, tipi, pd.Timestamp(f"{pon.year}-01-01", tz=TZ), let)
        n = napovej_teden(df, vreme, tipi, pon, par_leto[pon.year])
        dej = df["Neto"].reindex(n.index)
        vrstice.append({"teden": pon, "dejansko": dej.mean(),
                        "model": n["Neto"].mean(), "naivna": n["Naivna"].mean(),
                        "povp2": n["Povp2"].mean(),
                        "mae15_model": (n["Neto"] - dej).abs().mean(),
                        "mae15_naivna": (n["Naivna"] - dej).abs().mean(),
                        "mae15_povp2": (n["Povp2"] - dej).abs().mean()})
        napake15.append(pd.DataFrame({"napaka": dej - n["Neto"], "pon": pon}))
    t = pd.DataFrame(vrstice).set_index("teden")
    return t, pd.concat(napake15), par_leto


# ---------------------------------------------------------------------------
# 5. GLAVNI DEL
# ---------------------------------------------------------------------------
def povzetek(t, maska, ime):
    t = t[maska]
    vr = {"tednov": len(t)}
    for m in ("model", "naivna", "povp2"):
        e = t["dejansko"] - t[m]
        vr[f"{m}: napaka tedna (povp. abs.)"] = e.abs().mean()
        vr[f"{m}: napaka 15-min (povp. abs.)"] = t[f"mae15_{m}"].mean()
    return pd.Series(vr, name=ime)


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    df, vreme, tipi = pripravi_podatke()
    print("Podatki do:", df.index.max())

    # --- test: različne dolžine učnega obdobja za parametre
    rezultati = {}
    for let in (1, 3, None):
        t, e15, par_leto = backtest(df, vreme, tipi, let)
        rezultati[let] = (t, e15, par_leto)
        ime = "vse od 2015" if let is None else f"{let} let"
        print(f"\nParametri ({ime}) po letih testa:")
        print(pd.DataFrame(par_leto).round(2).to_string())

    print("\nTEST – povprečna absolutna napaka, MW (15-min vrednosti, lokalni čas)")
    for let, (t, _, _) in rezultati.items():
        ime = "vse od 2015" if let is None else f"{let} let"
        jesen = t.index.month.isin([10, 11, 12])
        print(f"\n— parametri iz: {ime}")
        print(pd.concat([povzetek(t, slice(None), "vsi tedni 2023–2026"),
                         povzetek(t, jesen, "okt–dec"),
                         povzetek(t, t.index >= "2025-11-01", "zadnje leto")],
                        axis=1).round(0).to_string())

    # shrani rezultate testa za nadaljnje korake
    for let, (t, e15, _) in rezultati.items():
        ime = "vse" if let is None else f"{let}l"
        t.to_parquet(DATA / f"backtest_{ime}.parquet")
        e15.to_parquet(DATA / f"backtest_napake15_{ime}.parquet")

    # -----------------------------------------------------------------------
    # 6. NAPOVED ZA TEDEN 47 (parametri iz zadnjih 3 let)
    # -----------------------------------------------------------------------
    LET = 3
    par = oceni_parametre(df, vreme, tipi, T47, LET)
    print("\nParametri za teden 47 (zadnja 3 leta do 15. 11. 2026):",
          {k: round(v, 2) for k, v in par.items()})
    n = napovej_teden(df, vreme, tipi, T47, par)

    # razpon iz testa: napake v tednih okt–dec (dejansko − napoved)
    t, e15, _ = rezultati[LET]
    jesen = t[t.index.month.isin([10, 11, 12])]
    e_teden = jesen["dejansko"] - jesen["model"]
    q10, q90 = e_teden.quantile([0.1, 0.9])
    print(f"\nNapaka tedenskega povprečja (okt–dec, {len(jesen)} tednov): "
          f"povprečje {e_teden.mean():.0f}, 10 % {q10:.0f}, 90 % {q90:.0f} MW")
    e15 = e15[e15["pon"].dt.month.isin([10, 11, 12])]
    pas = e15.groupby(e15.index.hour)["napaka"].quantile([0.1, 0.9]).unstack()
    n["spodaj"] = n["Neto"] + pas[0.1].reindex(n.index.hour).values
    n["zgoraj"] = n["Neto"] + pas[0.9].reindex(n.index.hour).values

    # vreme: zadnja 2 tedna proti tednu 47
    dnevi = pd.date_range("2026-11-02", "2026-11-22", freq="D").date
    print("\nVreme po dnevih (dnevna povprečna temperatura °C, dnevna vsota sevanja "
          "Wh/m²; 2.–15. 11. izmerjeno, 16.–22. 11. napoved s 14. 11.)")
    print(vreme.reindex(dnevi).round(1).T.to_string())

    # tabela po kosih: dnevna povprečja
    kosi = ["Poraba", "Paks", "Plin", "Sonce", "Premog", "Biomasa", "Veter",
            "Ostalo", "Uskladitev", "Neto"]
    dnevno = n[kosi].groupby(n.index.date).mean()
    dnevno.index = [f"{DNI[i]} {d:%d.%m.}" for i, d in enumerate(dnevno.index)]
    dnevno.loc["TEDEN 47"] = n[kosi].mean()
    peak = (n.index.day_of_week < 5) & (n.index.hour >= 8) & (n.index.hour < 20)
    dnevno.loc["  peak (pon–pet 8–20)"] = n.loc[peak, kosi].mean()
    dnevno.loc["  offpeak"] = n.loc[~peak, kosi].mean()
    print("\nNAPOVED TEDNA 47 po kosih, MW (dnevna povprečja 15-min vrednosti, "
          "lokalni čas, + = izvoz)")
    print(dnevno.round(0).to_string())

    # zadnja dva tedna (dejansko), za primerjavo
    ref = df[(df.index >= "2026-11-02") & (df.index < T47)]
    ref = ref[kosi].groupby((ref.index.normalize() - pd.to_timedelta(
        ref.index.day_of_week, unit="D")).date).mean()
    ref.index = ["teden 45 (dejansko)", "teden 46 (dejansko)"]
    print("\n" + ref.round(0).to_string())
    sr = n["Neto"].mean()
    print(f"\nTEDEN 47: neto {sr:.0f} MW, razpon (80 %) {sr + q10:.0f} do {sr + q90:.0f} MW")

    # zamrznjena napoved (pred ogledom dejanskih podatkov za 16. 11.+)
    n.to_parquet(DATA / "napoved_t47_zamrznjena.parquet")
    n[["Neto", "spodaj", "zgoraj", "Poraba", "Paks", "Plin", "Sonce"]].round(1) \
        .to_csv(KOREN / "report" / "napoved_t47.csv")
    print("  zamrznjeno: data/napoved_t47_zamrznjena.parquet, report/napoved_t47.csv")

    # --- GRAF b1: profil napovedi s pasom + zadnji teden
    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    x = np.arange(len(n)) / 96
    ax.fill_between(x, n["spodaj"], n["zgoraj"], color=PALETA[0], alpha=0.18,
                    lw=0, label="razpon (10–90 %)")
    ax.plot(x, n["Neto"], color=PALETA[0], lw=1.4, label="napoved teden 47")
    t46 = df[(df.index >= "2026-11-09") & (df.index < T47)]["Neto"]
    ax.plot(np.arange(len(t46)) / 96, t46.values, color="#888888", lw=0.9,
            label="teden 46 (dejansko)")
    ax.axhline(0, color="#333333", lw=0.8)
    ax.set_xticks(np.arange(7) + 0.5, [f"{DNI[i]}\n{16 + i}. 11." for i in range(7)])
    ax.set_xticks(np.arange(8), minor=True)
    ax.tick_params(axis="x", which="major", length=0)
    ax.grid(axis="x", which="minor", color="#e5e5e5")
    ax.grid(axis="x", which="major", visible=False)
    ax.set_ylabel("neto [MW]")
    ax.set_title(f"Napoved neto pozicije, teden 47 (povprečje {sr:.0f} MW; "
                 "+ izvoz, − uvoz)", pad=24)
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    fig.text(0.99, -0.03, "15-min vrednosti, lokalni čas. Razpon iz testa na "
             "tednih okt–dec 2023–2026.", ha="right", fontsize=7, color="#666666")
    shrani(fig, "b1_napoved_t47", FIG_B)

    # --- GRAF b2: test – dejansko vs napoved (tedenska povprečja)
    tt = t[t.index >= "2025-01-01"]
    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    ax.plot(tt.index, tt["dejansko"], color="#333333", lw=1.6, label="dejansko")
    ax.plot(tt.index, tt["model"], color=PALETA[0], lw=1.2, label="model po kosih")
    ax.plot(tt.index, tt["naivna"], color=PALETA[1], lw=1.0, ls="--",
            label="naivna (kot prejšnji teden)")
    ax.set_ylabel("tedensko povprečje neto [MW]")
    ax.set_title("Test: napoved vsakega tedna samo s preteklimi podatki", pad=24)
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    fig.text(0.99, -0.03, "Pri testu je uporabljena izmerjena temperatura, zato je "
             "test nekoliko preveč optimističen.", ha="right", fontsize=7,
             color="#666666")
    shrani(fig, "b2_test_tedni", FIG_B)
