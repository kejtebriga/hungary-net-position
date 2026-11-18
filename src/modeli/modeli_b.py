"""
b) VSI MODELI za neto pozicijo + skupni test na 202 tednih + napoved tedna 47.

Vsak model se »postavi« v nedeljo zvečer pred tednom in napove 7 dnevnih povprečij
neto pozicije (MW, + = izvoz). Iz dnevnih dobimo tedensko (povprečje 7 dni) in
15-min profil (dnevna vrednost + tipična oblika dneva iz zadnjih 2 tednov).

Skupine modelov:
  1  naivni            – kot prejšnji teden (isti dan v tednu)
  2  sezonski          – isti dan pred 52 tedni
  3a povp. 2 tedna     – povprečje zadnjih 2 tednov po tipu dneva (delovni/sob/ned)
  3b povp. 4 tedne
  3c 2 tedna + 3 dni   – oblika iz 2 tednov, raven iz zadnjih 3 dni
  4  temperatura       – 3a + vpliv spremembe temperature        (en dejavnik)
  5  sonce             – 3a + vpliv spremembe sončnega sevanja   (en dejavnik)
  6  Paks              – 3a + vpliv stanja Paksa (zadnji 3 dnevi) (en dejavnik)
  7  plin              – 3a + vpliv ravni plina (zadnji 3 dnevi)  (en dejavnik)
  8  preostala poraba  – 3a + vpliv spremembe (poraba − sonce − veter − Paks)
  9  regresija         – ena linearna enačba z vsemi dejavniki
  10a po formuli       – neto = proizvodnja − poraba, vsak vir posebej (plin 2 tedna)
  10b po formuli       – enako, plin iz zadnjih 3 dni
  11 podobni dnevi     – povprečje 10 najbolj podobnih preteklih dni
  12 nevronska mreža   – isti vhodi kot 9, nelinearno (povprečje 5 mrež)
  12p nevronska mreža  – napove vseh 96 četrtur dneva naenkrat
  13 kratko + dolgo    – povprečje 10a in 10b
  14 kombinacija       – povprečje 9, 10b in 11 (izbrano vnaprej, ne po testu)

Pravila: za vsak teden le podatki do nedelje pred njim; parametri se ocenijo iz
zadnjih 3 let pred tem tednom (regresija vsak teden, mreže vsake 4 tedne,
model po formuli enkrat na leto). Pri testu je uporabljeno izmerjeno vreme
(za teden 47 pa napoved s 14. 11.) – test je zato nekoliko preveč optimističen.

Zagon: .venv/bin/python src/modeli/modeli_b.py
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from napoved_b import (DATA, KOREN, TZ, napovej_teden, oceni_parametre,
                       pripravi_podatke)

warnings.filterwarnings("ignore")
T47 = pd.Timestamp("2026-11-16")
TEDNI_TEST = pd.date_range("2023-01-02", "2026-11-09", freq="W-MON")
D = pd.Timedelta(days=1)
LET_UCENJA = 3
VHODI = ["sob", "ned", "HDD", "CDD", "sev", "HDD_lw", "CDD_lw", "sev_lw",
         "neto_lw", "neto14", "paks3", "paks14", "plin3", "plin14"]


# ---------------------------------------------------------------------------
# 1. PODATKI: dnevna tabela + vhodi, znani v nedeljo pred tednom
# ---------------------------------------------------------------------------
def dnevna_tabela(df, vreme, tipi):
    dan = df.resample("D").mean()
    dan.index = dan.index.tz_localize(None)
    dnevi = pd.date_range("2015-01-01", T47 + 6 * D, freq="D")
    dan = dan.reindex(dnevi)
    vr = vreme.copy()
    vr.index = pd.to_datetime(vr.index)
    dan = dan.join(vr)
    tip = tipi.copy()
    tip.index = pd.to_datetime(tip.index)
    dan["tip"] = tip.reindex(dan.index).values
    dan["HDD"] = np.maximum(15.5 - dan["T"], 0)      # stopinje ogrevanja
    dan["CDD"] = np.maximum(dan["T"] - 22, 0)        # stopinje hlajenja
    dan["Preostala"] = dan["Poraba"] - dan["Sonce"] - dan["Veter"] - dan["Paks"]
    return dan


def vhodi_tedna(dan, W):
    """Vhodi za 7 dni tedna z začetkom W (ponedeljek) – vse znano do nedelje."""
    d = dan.loc[W:W + 6 * D].copy()
    zad3 = dan.loc[W - 3 * D:W - D]
    zad14 = dan.loc[W - 14 * D:W - D]
    lw = dan.loc[W - 7 * D:W - D]
    d["izvor"] = W
    d["sob"] = (d["tip"] == "sob").astype(float)
    d["ned"] = (d["tip"] == "ned").astype(float)
    d["sev"] = d["sevanje"]
    d["HDD_lw"], d["CDD_lw"] = lw["HDD"].values, lw["CDD"].values
    d["sev_lw"], d["neto_lw"] = lw["sevanje"].values, lw["Neto"].values
    d["neto14"] = zad14["Neto"].mean()
    d["paks3"], d["paks14"] = zad3["Paks"].mean(), zad14["Paks"].mean()
    d["plin3"], d["plin14"] = zad3["Plin"].mean(), zad14["Plin"].mean()
    return d


# ---------------------------------------------------------------------------
# 2. POMOŽNO: izhodišče (2 tedna po tipu dneva) in občutljivosti
# ---------------------------------------------------------------------------
def po_tipu(dan, W, stolpec, dni=14):
    """povprečje stolpca v zadnjih 'dni' dneh, ločeno po tipu dneva"""
    b = dan.loc[W - dni * D:W - D]
    return b.groupby("tip")[stolpec].mean()


def obcutljivost(dan, W, y, x):
    """Koliko se y spremeni, ko se x spremeni za 1 (primerjava z istim dnem
    teden prej, zadnja 3 leta) – premica skozi 0, en ali več x."""
    b = dan.loc[W - pd.DateOffset(years=LET_UCENJA):W - D]
    dy = (b[y] - b[y].shift(7))
    dx = (b[x] - b[x].shift(7))
    ok = dy.notna() & dx.notna().all(axis=1)
    k, *_ = np.linalg.lstsq(dx[ok].values, dy[ok].values, rcond=None)
    return k


# ---------------------------------------------------------------------------
# 3. MODELI (vsak vrne 7 dnevnih vrednosti)
# ---------------------------------------------------------------------------
def model_povp(dan, W, dni):
    t = vhodi_tedna(dan, W)
    return po_tipu(dan, W, "Neto", dni).reindex(t["tip"]).values


def model_3c(dan, W):
    t = vhodi_tedna(dan, W)
    p2 = po_tipu(dan, W, "Neto")
    zad3 = dan.loc[W - 3 * D:W - D]
    zamik = zad3["Neto"].mean() - p2.reindex(zad3["tip"]).mean()
    return p2.reindex(t["tip"]).values + zamik


def model_en_dejavnik(dan, W, dejavnik):
    t = vhodi_tedna(dan, W)
    osnova = po_tipu(dan, W, "Neto").reindex(t["tip"]).values
    if dejavnik == "temperatura":
        k = obcutljivost(dan, W, "Neto", ["HDD", "CDD"])
        x_bod = t[["HDD", "CDD"]].values
        x_baz = np.column_stack([po_tipu(dan, W, c).reindex(t["tip"]).values
                                 for c in ("HDD", "CDD")])
        return osnova + (x_bod - x_baz) @ k
    stolpec, prihodnost = {"sonce": ("sevanje", t["sevanje"].values),
                           "Paks": ("Paks", t["paks3"].values),
                           "plin": ("Plin", t["plin3"].values)}[dejavnik]
    k = obcutljivost(dan, W, "Neto", [stolpec])[0]
    return osnova + k * (prihodnost - po_tipu(dan, W, stolpec).reindex(t["tip"]).values)


def model_preostala(dan, W):
    t = vhodi_tedna(dan, W)
    tip = t["tip"]
    osnova = po_tipu(dan, W, "Neto").reindex(tip).values
    k_por = obcutljivost(dan, W, "Poraba", ["HDD", "CDD"])     # MW porabe na stopinjo
    k_son = obcutljivost(dan, W, "Sonce", ["sevanje"])[0]      # MW sonca na Wh/m²
    k_neto = obcutljivost(dan, W, "Neto", ["Preostala"])[0]    # MW neto na MW preostale
    d_por = (t[["HDD", "CDD"]].values - np.column_stack(
        [po_tipu(dan, W, c).reindex(tip).values for c in ("HDD", "CDD")])) @ k_por
    d_son = k_son * (t["sevanje"].values - po_tipu(dan, W, "sevanje").reindex(tip).values)
    d_paks = t["paks3"].values - po_tipu(dan, W, "Paks").reindex(tip).values
    return osnova + k_neto * (d_por - d_son - d_paks)


def ucni_vhodi(F, W):
    u = F[(F["izvor"] < W) & (F["izvor"] >= W - pd.DateOffset(years=LET_UCENJA))]
    return u.dropna(subset=VHODI + ["Neto"])


def model_regresija(F, W, vrni_koef=False):
    u = ucni_vhodi(F, W)
    X = np.column_stack([np.ones(len(u)), u[VHODI].values])
    k, *_ = np.linalg.lstsq(X, u["Neto"].values, rcond=None)
    t = F[F["izvor"] == W]
    napoved = np.column_stack([np.ones(len(t)), t[VHODI].values]) @ k
    return (napoved, dict(zip(["konstanta"] + VHODI, k))) if vrni_koef else napoved


def model_podobni(dan, W, k=10):
    t = vhodi_tedna(dan, W)
    zgod = dan.loc[W - pd.DateOffset(years=2):W - D].dropna(subset=["Neto", "T", "sevanje"])
    out = []
    for d, vr in t.iterrows():
        kand = zgod[zgod["tip"] == vr["tip"]]
        razlika_dni = np.abs(kand.index.dayofyear - d.dayofyear)
        kand = kand[np.minimum(razlika_dni, 365 - razlika_dni) <= 45]   # letni čas
        razdalja = np.sqrt(((kand["T"] - vr["T"]) / 4) ** 2 +
                           ((kand["sevanje"] - vr["sevanje"]) / 1000) ** 2)
        out.append(kand.loc[razdalja.nsmallest(k).index, "Neto"].mean())
    return np.array(out)


class Mreze:
    """Povprečje več majhnih nevronskih mrež (2 skriti plasti), z
    standardizacijo vhodov/izhodov in zgodnjo ustavitvijo."""
    def __init__(self, n=5, plasti=(16, 8)):
        self.n, self.plasti = n, plasti

    def nauci(self, X, Y):
        self.sx, self.sy = StandardScaler().fit(X), StandardScaler().fit(Y)
        Xs, Ys = self.sx.transform(X), self.sy.transform(Y)
        if Ys.shape[1] == 1:
            Ys = Ys.ravel()
        self.mreze = [MLPRegressor(hidden_layer_sizes=self.plasti, alpha=1e-3, early_stopping=True,
                                   max_iter=3000, random_state=s).fit(Xs, Ys)
                      for s in range(self.n)]
        return self

    def napovej(self, X):
        p = np.mean([m.predict(self.sx.transform(X)) for m in self.mreze], axis=0)
        return self.sy.inverse_transform(p.reshape(len(X), -1))


def profili_96(df, F):
    """Tabela: za vsak dan 96 četrtur neto (dnevi s premikom ure izpuščeni)."""
    n = df["Neto"].copy()
    n.index = n.index.tz_localize(None)
    tab = n.groupby([n.index.normalize(), n.index.strftime("%H:%M")]).mean().unstack()
    return tab.dropna()


def oblika_dneva(df, W):
    """tipična oblika dneva (odstopanje od dnevnega povprečja) iz zadnjih 2 tednov"""
    Wl = W.tz_localize(TZ)
    b = df.loc[Wl - pd.DateOffset(days=14):Wl - pd.Timedelta(minutes=15), ["Neto"]].copy()
    b["dan"] = b.index.normalize()
    b["termin"] = b.index.strftime("%H:%M")
    b["odst"] = b["Neto"] - b.groupby("dan")["Neto"].transform("mean")
    return b, b.groupby("termin")["odst"].mean()


# ---------------------------------------------------------------------------
# 4. EN TEDEN, VSI MODELI
# ---------------------------------------------------------------------------
IMENA = {"1": "naivni", "2": "sezonski", "3a": "povp. 2 tedna", "3b": "povp. 4 tedne",
         "3c": "2 tedna + raven 3 dni", "4": "en dejavnik: temperatura",
         "5": "en dejavnik: sonce", "6": "en dejavnik: Paks", "7": "en dejavnik: plin",
         "8": "preostala poraba", "9": "linearna regresija",
         "10a": "po formuli (plin 2 tedna)", "10b": "po formuli (plin 3 dni)",
         "11": "podobni dnevi", "12": "nevronska mreža (dnevno)",
         "12p": "nevronska mreža (profil 96)", "13": "kratko+dolgo (10a,10b)",
         "14": "kombinacija (9,10b,11)"}


def vsi_modeli(df, vreme, tipi, dan, F, P96, W, par10, mreze):
    dn = {}
    t = F[F["izvor"] == W]
    dn["1"] = t["neto_lw"].values
    dn["2"] = dan["Neto"].reindex(t.index - 364 * D).values
    dn["3a"] = model_povp(dan, W, 14)
    dn["3b"] = model_povp(dan, W, 28)
    dn["3c"] = model_3c(dan, W)
    for st, dej in (("4", "temperatura"), ("5", "sonce"), ("6", "Paks"), ("7", "plin")):
        dn[st] = model_en_dejavnik(dan, W, dej)
    dn["8"] = model_preostala(dan, W)
    dn["9"] = model_regresija(F, W)
    Wl = W.tz_localize(TZ)
    q15 = {}
    for st, plin in (("10a", "2t"), ("10b", "3d")):
        n = napovej_teden(df, vreme, tipi, Wl, par10, plin=plin)
        q15[st] = n["Neto"].values
        dn[st] = n["Neto"].groupby(n.index.date).mean().values
    dn["11"] = model_podobni(dan, W)
    dn["12"] = mreze["dnevno"].napovej(t[VHODI].values).ravel()
    p96 = mreze["profil"].napovej(t[VHODI].values)           # 7 × 96
    dn["12p"] = p96.mean(axis=1)
    dn["13"] = (dn["10a"] + dn["10b"]) / 2
    dn["14"] = (dn["9"] + dn["10b"] + dn["11"]) / 3
    dnevno = pd.DataFrame(dn, index=t.index)

    # 15-min: dnevna vrednost + oblika dneva (razen modelov z lastnim profilom)
    cilj = pd.date_range(Wl, Wl + pd.DateOffset(days=7), freq="15min", inclusive="left")
    termin = cilj.strftime("%H:%M")
    _, oblika = oblika_dneva(df, W)
    datum = pd.DatetimeIndex(cilj.tz_localize(None).normalize())
    q = pd.DataFrame(index=cilj)
    for st in dnevno:
        q[st] = dnevno[st].reindex(datum).values + oblika.reindex(termin).values
    for st in q15:
        q[st] = q15[st]
    q["13"] = (q["10a"] + q["10b"]) / 2
    q["12p"] = pd.DataFrame(p96, index=t.index, columns=P96.columns) \
        .stack().reindex(pd.MultiIndex.from_arrays([datum, termin])).values
    return dnevno, q


def nauci_mreze(F, P96, W):
    u = ucni_vhodi(F, W)
    dnevno = Mreze(5).nauci(u[VHODI].values, u[["Neto"]].values)
    u96 = u[u.index.isin(P96.index)]
    profil = Mreze(3, (32, 16)).nauci(u96[VHODI].values, P96.loc[u96.index].values)
    return {"dnevno": dnevno, "profil": profil}


# ---------------------------------------------------------------------------
# 5. TEST + NAPOVED
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    pd.set_option("display.width", 220)
    df, vreme, tipi = pripravi_podatke()
    dan = dnevna_tabela(df, vreme, tipi)
    izvori = pd.date_range("2019-12-30", T47, freq="W-MON")
    F = pd.concat([vhodi_tedna(dan, W) for W in izvori])
    P96 = profili_96(df, F)

    vrstice, napake15, mreze, par10 = [], [], None, {}
    for i, W in enumerate(TEDNI_TEST):
        if i % 4 == 0:
            mreze = nauci_mreze(F, P96, W)
        if W.year not in par10:
            par10[W.year] = oceni_parametre(df, vreme, tipi,
                                            pd.Timestamp(f"{W.year}-01-01", tz=TZ), 3)
        dnevno, q = vsi_modeli(df, vreme, tipi, dan, F, P96, W, par10[W.year], mreze)
        dej_d = dan["Neto"].reindex(dnevno.index)
        dej_q = df["Neto"].reindex(q.index)
        for st in dnevno:
            vrstice.append({"teden": W, "model": st, "dejansko": dej_d.mean(),
                            "napoved": dnevno[st].mean(),
                            "mae_dan": (dnevno[st] - dej_d).abs().mean(),
                            "mae_15": (q[st] - dej_q).abs().mean()})
        e = q.sub(dej_q, axis=0).mul(-1)                 # dejansko − napoved
        e["teden"] = W
        napake15.append(e)
        if i % 20 == 0:
            print(f"  test: {W.date()} ({i + 1}/{len(TEDNI_TEST)})", flush=True)
    R = pd.DataFrame(vrstice)
    R["napaka_teden"] = R["dejansko"] - R["napoved"]
    R.to_parquet(DATA / "b_modeli_test.parquet")
    pd.concat(napake15).to_parquet(DATA / "b_modeli_napake15.parquet")

    # --- povzetek testa
    def povzetek(r):
        g = r.groupby("model")
        t = pd.DataFrame({"teden": g["napaka_teden"].apply(lambda e: e.abs().mean()),
                          "dan": g["mae_dan"].mean(), "15 min": g["mae_15"].mean()})
        return t
    vsi = povzetek(R)
    jesen = povzetek(R[R["teden"].dt.month.isin([10, 11, 12])])
    tab = pd.concat({"vsi tedni": vsi, "okt–dec": jesen}, axis=1)
    for obd in ("vsi tedni", "okt–dec"):
        tab[(obd, "rel. teden")] = tab[(obd, "teden")] / tab.loc["1", (obd, "teden")]
    tab.index = [f"{i:>3} {IMENA[i]}" for i in tab.index]
    tab = tab.sort_values(("vsi tedni", "teden"))
    print("\nTEST 202 tednov (2. 1. 2023 – 15. 11. 2026): povprečna absolutna napaka "
          "neto, MW; rel. = glede na naivni model (1 = enako dober)")
    print(tab.round(2).to_string())
    tab.to_csv(DATA / "b_modeli_povzetek.csv")

    # --- napoved tedna 47 z vsemi modeli
    mreze = nauci_mreze(F, P96, T47)
    par47 = oceni_parametre(df, vreme, tipi, T47.tz_localize(TZ), 3)
    dnevno, q = vsi_modeli(df, vreme, tipi, dan, F, P96, T47, par47, mreze)
    _, koef = model_regresija(F, T47, vrni_koef=True)
    print("\nKoeficienti regresije (model 9) za teden 47:",
          {k: round(v, 2) for k, v in koef.items()})
    dnevno.index = [d.strftime("%a %d.%m.") for d in dnevno.index]
    dnevno.loc["TEDEN 47"] = dnevno.mean()
    print("\nNAPOVED TEDNA 47 po modelih, MW (dnevna povprečja, + = izvoz)")
    print(dnevno.T.rename(index=IMENA).round(0).to_string())
    dnevno.to_parquet(DATA / "b_napovedi_t47_dnevno.parquet")
    q.to_parquet(DATA / "b_napovedi_t47_15min.parquet")
    print("  zamrznjeno: data/b_napovedi_t47_dnevno.parquet, data/b_napovedi_t47_15min.parquet")
