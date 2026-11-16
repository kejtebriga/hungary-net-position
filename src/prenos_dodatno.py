"""
Dodatni podatki (dopolnilo k prenos_podatkov.py), od 2023 naprej:

  Energy-Charts:
    - nameščena moč po virih, HU (letno)                     -> namescena_moc.parquet
    - uradne dan-vnaprej napovedi HU: sonce, poraba           -> napovedi_hu.parquet
    - dan-vnaprej cene sosednjih in vplivnih območij          -> cene_sosedi.parquet
    - proizvodnja in poraba Nemčije (veter, sonce ...)        -> proizvodnja_de.parquet
  Yahoo Finance:
    - cena plina TTF (front month, EUR/MWh, dnevno)           -> plin_ttf.parquet
  Open-Meteo:
    - veter na 100 m v severni Nemčiji (zgodovina + napoved)  -> veter_de.parquet

Vsak kos se sproti shrani v data/kosi_dodatno/, da se ob prekinitvi nadaljuje.
Neobvezni viri (npr. območje, ki ga API nima) ne ustavijo prenosa, ampak se izpišejo.

Zagon: .venv/bin/python src/prenos_dodatno.py
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

KOREN = Path(__file__).resolve().parents[1]
DATA = KOREN / "data"
KOSI = DATA / "kosi_dodatno"
KOSI.mkdir(parents=True, exist_ok=True)

EC = "https://api.energy-charts.info"
ZACETEK = date(2023, 1, 1)
KONEC = date.today() + timedelta(days=1)
PREMOR = 5  # s med zahtevki (API ima strogo omejitev hitrosti)

seja = requests.Session()
seja.headers["User-Agent"] = "Mozilla/5.0 (research-script)"


def _get(url: str, params: dict, poskusi: int = 6) -> dict:
    napaka = None
    for i in range(poskusi):
        try:
            r = seja.get(url, params=params, timeout=180)
            if r.status_code == 200:
                return r.json()
            napaka = f"HTTP {r.status_code}: {r.text[:60]}"
            if r.status_code == 404 or "no content" in r.text:
                break  # ni podatkov – ponavljanje nima smisla
        except requests.exceptions.RequestException as e:
            napaka = repr(e)
        print(f"    ponovni poskus {i + 1}/{poskusi} ({napaka})", flush=True)
        time.sleep(15 * (i + 1))
    raise RuntimeError(napaka)


def _obdobja(zac: date, kon: date, meseci: int):
    d = zac.replace(day=1)
    while d <= kon:
        m = d.month - 1 + meseci
        nasl = date(d.year + m // 12, m % 12 + 1, 1)
        yield max(d, zac), min(nasl - timedelta(days=1), kon)
        d = nasl


def _kos(ime: str, zac: date, prenos, osvezi: bool) -> pd.DataFrame | None:
    """Vrne kos iz predpomnilnika ali ga prenese in shrani."""
    pot = KOSI / f"{ime}_{zac:%Y-%m}.parquet"
    if pot.exists() and not osvezi:
        return pd.read_parquet(pot)
    try:
        df = prenos()
    except Exception as e:  # noqa: BLE001
        print(f"    !! {ime} {zac:%Y-%m} preskočeno: {e}", flush=True)
        return None
    df.to_parquet(pot)
    time.sleep(PREMOR)
    return df


def _zbirka(ime: str, meseci: int, prenos_fn) -> pd.DataFrame | None:
    obd = list(_obdobja(ZACETEK, KONEC, meseci))
    deli = []
    for n, (zac, kon) in enumerate(obd):
        if zac.month == 1 or n == 0:
            print(f"  {ime}: {zac:%Y} ...", flush=True)
        df = _kos(ime, zac, lambda: prenos_fn(zac, kon), osvezi=(n == len(obd) - 1))
        if df is not None:
            deli.append(df)
    if not deli:
        return None
    out = pd.concat(deli).sort_index()
    return out[~out.index.duplicated(keep="last")]


def _cas(js):
    return pd.to_datetime(js["unix_seconds"], unit="s", utc=True)


# --- 1. nameščena moč --------------------------------------------------------
def namescena_moc():
    print("Nameščena moč HU")
    js = _get(f"{EC}/installed_power", {"country": "hu", "time_step": "yearly"})
    df = pd.DataFrame({s["name"]: s["data"] for s in js["production_types"]},
                      index=pd.Index(js["time"], name="leto"))
    df.to_parquet(DATA / "namescena_moc.parquet")
    print(f"  -> {df.shape[0]} let, {df.shape[1]} virov  [GW]")
    time.sleep(PREMOR)


# --- 2. uradne napovedi HU ---------------------------------------------------
def napovedi_hu():
    print("Uradne dan-vnaprej napovedi HU")
    stolpci = {}
    for tip in ("solar", "load"):
        def prenos(zac, kon, tip=tip):
            js = _get(f"{EC}/public_power_forecast",
                      {"country": "hu", "production_type": tip, "forecast_type": "day-ahead",
                       "start": zac.isoformat(), "end": kon.isoformat()})
            return pd.DataFrame({f"napoved_{tip}": js["forecast_values"]}, index=_cas(js))
        df = _zbirka(f"napoved_{tip}", 3, prenos)
        if df is not None:
            stolpci[tip] = df
    out = pd.concat(stolpci.values(), axis=1)
    out.to_parquet(DATA / "napovedi_hu.parquet")
    print(f"  -> {len(out):,} vrstic, do {out.index.max()}  [MW]")


# --- 3. cene sosedov ---------------------------------------------------------
OBMOCJA = ["HU", "AT", "SK", "RO", "HR", "SI", "RS", "CZ", "PL", "DE-LU", "IT-North"]


def cene_sosedi():
    print("Cene območij")
    stolpci = []
    for bzn in OBMOCJA:
        def prenos(zac, kon, bzn=bzn):
            js = _get(f"{EC}/price", {"bzn": bzn, "start": zac.isoformat(), "end": kon.isoformat()})
            return pd.DataFrame({bzn: js["price"]}, index=_cas(js))
        df = _zbirka(f"cena_{bzn}", 3, prenos)
        if df is not None:
            stolpci.append(df)
    out = pd.concat(stolpci, axis=1).sort_index()
    out.to_parquet(DATA / "cene_sosedi.parquet")
    print(f"  -> {len(out):,} vrstic, območja: {list(out.columns)}  [EUR/MWh]")


# --- 4. Nemčija: proizvodnja --------------------------------------------------
def proizvodnja_de():
    print("Proizvodnja DE")

    def prenos(zac, kon):
        js = _get(f"{EC}/public_power", {"country": "de", "start": zac.isoformat(), "end": kon.isoformat()})
        df = pd.DataFrame({s["name"]: s["data"] for s in js["production_types"]}, index=_cas(js))
        keep = [c for c in df.columns if c in
                ("Wind onshore", "Wind offshore", "Solar", "Load", "Residual load",
                 "Fossil gas", "Fossil brown coal / lignite", "Fossil hard coal",
                 "Cross border electricity trading")]
        return df[keep]
    out = _zbirka("proizvodnja_de", 1, prenos)
    out.to_parquet(DATA / "proizvodnja_de.parquet")
    print(f"  -> {len(out):,} vrstic, do {out.index.max()}  [MW]")


# --- 5. plin TTF ---------------------------------------------------------------
def plin_ttf():
    print("Plin TTF (Yahoo Finance, TTF=F)")
    js = _get("https://query1.finance.yahoo.com/v8/finance/chart/TTF=F",
              {"range": "5y", "interval": "1d"})
    r = js["chart"]["result"][0]
    df = pd.DataFrame({"ttf": r["indicators"]["quote"][0]["close"]},
                      index=pd.to_datetime(r["timestamp"], unit="s", utc=True).normalize())
    df = df.dropna()
    df.to_parquet(DATA / "plin_ttf.parquet")
    print(f"  -> {len(df):,} dni, {df.index.min():%Y-%m-%d} – {df.index.max():%Y-%m-%d}, "
          f"zadnja {df['ttf'].iloc[-1]:.2f} EUR/MWh")


# --- 6. veter v severni Nemčiji (Open-Meteo) ---------------------------------
TOCKE_DE = {"Schleswig-Holstein": (54.4, 9.5), "Spodnja Saška": (53.0, 8.0),
            "Meklenburg": (53.8, 12.5), "Brandenburg": (52.5, 13.5)}


def veter_de():
    print("Veter DE (Open-Meteo)")
    deli = []
    for ime, (lat, lon) in TOCKE_DE.items():
        zg = _get("https://archive-api.open-meteo.com/v1/archive", {
            "latitude": lat, "longitude": lon, "hourly": "wind_speed_100m",
            "start_date": ZACETEK.isoformat(),
            "end_date": (date.today() - timedelta(days=6)).isoformat(), "timezone": "UTC"})
        np_ = _get("https://api.open-meteo.com/v1/forecast", {
            "latitude": lat, "longitude": lon, "hourly": "wind_speed_100m",
            "past_days": 10, "forecast_days": 16, "timezone": "UTC"})
        for js, vir in ((zg, "arhiv"), (np_, "napoved")):
            df = pd.DataFrame(js["hourly"])
            df["cas"] = pd.to_datetime(df.pop("time"), utc=True)
            df["tocka"], df["vir"] = ime, vir
            deli.append(df)
        time.sleep(1)
    vse = pd.concat(deli).sort_values("vir").drop_duplicates(["cas", "tocka"], keep="first")
    out = vse.groupby("cas").agg(veter_100m=("wind_speed_100m", "mean"),
                                 vir=("vir", lambda s: "napoved" if (s == "napoved").any() else "arhiv"))
    out.to_parquet(DATA / "veter_de.parquet")
    print(f"  -> {len(out):,} ur, do {out.index.max()}  [km/h]")


if __name__ == "__main__":
    for korak in (plin_ttf, veter_de, namescena_moc, napovedi_hu, cene_sosedi, proizvodnja_de):
        try:
            korak()
        except Exception as e:  # noqa: BLE001
            print(f"!! {korak.__name__} ni uspel: {e}", flush=True)
    print("Končano.")
