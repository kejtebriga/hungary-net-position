"""
Prenos podatkov za madžarski elektroenergetski sistem.

Viri (brez API ključa):
  - Energy-Charts (Fraunhofer ISE, podatki iz ENTSO-E): https://api.energy-charts.info
      * public_power : proizvodnja po virih + poraba (Load)       [MW]
      * cbet         : čezmejna izmenjava po mejah                [GW, + = UVOZ v HU]
                       (preverjeno: korelacija z (proizvodnja − poraba) je −0,95)
      * price        : dan-vnaprej cena za ponudbeno območje HU   [EUR/MWh]
  - Open-Meteo: vreme (zgodovina + napoved) za 5 madžarskih mest

Rezultat: datoteke .parquet v mapi data/ (UTC časovni žigi).
Zagon:  .venv/bin/python src/prenos_podatkov.py
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

KOREN = Path(__file__).resolve().parents[1]
DATA = KOREN / "data"
DATA.mkdir(exist_ok=True)

EC = "https://api.energy-charts.info"
# Od 2015 naprej (začetek podatkov ENTSO-E). Dolga zgodovina služi analizi trendov (a);
# za napovedni model (b) uporabimo le zadnja leta, ker se je sistem močno spremenil
# (razmah sončnih elektrarn, energetska kriza 2022).
ZACETEK = date(2015, 1, 1)
KONEC = date.today() + timedelta(days=1)  # vključno z jutrišnjim dnem (cene DA so že znane)

seja = requests.Session()
seja.headers["User-Agent"] = "research-script"


def _get(url: str, params: dict, poskusi: int = 6) -> dict:
    """GET z ponovitvami: API občasno vrne 429/5xx ali prekine povezavo."""
    napaka = None
    for i in range(poskusi):
        try:
            r = seja.get(url, params=params, timeout=120)
            if r.status_code == 200:
                return r.json()
            napaka = f"HTTP {r.status_code}"
        except requests.exceptions.RequestException as e:
            napaka = repr(e)
        print(f"    ponovni poskus {i + 1}/{poskusi} ({napaka})", flush=True)
        time.sleep(10 * (i + 1))
    raise RuntimeError(f"Prenos ni uspel: {url} {params} -> {napaka}")


def _meseci(zac: date, kon: date):
    """Razdeli obdobje na mesečne kose (API ne mara predolgih zahtev)."""
    d = zac.replace(day=1)
    while d <= kon:
        nasl = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        yield max(d, zac), min(nasl - timedelta(days=1), kon)
        d = nasl


def _v_df(js: dict, kljuc_seznama: str) -> pd.DataFrame:
    cas = pd.to_datetime(js["unix_seconds"], unit="s", utc=True)
    stolpci = {s["name"]: s["data"] for s in js[kljuc_seznama]}
    return pd.DataFrame(stolpci, index=cas)


def prenesi_energy_charts() -> None:
    # Vsak mesec se sproti shrani v data/kosi/, da se ob prekinitvi prenos
    # nadaljuje tam, kjer se je ustavil. Zadnja dva meseca se vedno osvežita
    # (podatki se naknadno popravljajo, jutrišnji dan se dopolni).
    kosi_dir = DATA / "kosi"
    kosi_dir.mkdir(exist_ok=True)
    meseci = list(_meseci(ZACETEK, KONEC))
    for n, (zac, kon) in enumerate(meseci):
        osvezi = n >= len(meseci) - 2
        p = {"start": zac.isoformat(), "end": kon.isoformat()}
        print(f"  {zac:%Y-%m} ...", flush=True)

        def shrani(ime, prenos):
            pot = kosi_dir / f"{ime}_{zac:%Y-%m}.parquet"
            if pot.exists() and not osvezi:
                return
            prenos().to_parquet(pot)
            time.sleep(3)  # vljudnostni premor (API ima omejitev hitrosti, HTTP 429)

        shrani("proizvodnja", lambda: _v_df(
            _get(f"{EC}/public_power", {"country": "hu", **p}), "production_types"))
        shrani("meje", lambda: _v_df(
            _get(f"{EC}/cbet", {"country": "hu", **p}), "countries"))

        def cena():
            js = _get(f"{EC}/price", {"bzn": "HU", **p})
            return pd.DataFrame({"cena": js["price"]},
                                index=pd.to_datetime(js["unix_seconds"], unit="s", utc=True))
        shrani("cena", cena)

    for ime in ("proizvodnja", "meje", "cena"):
        seznam = [pd.read_parquet(f) for f in sorted(kosi_dir.glob(f"{ime}_*.parquet"))]
        df = pd.concat(seznam).sort_index()
        df = df[~df.index.duplicated(keep="last")]
        df.to_parquet(DATA / f"{ime}.parquet")
        print(f"  -> {ime}: {len(df):,} vrstic, {df.index.min()} – {df.index.max()}")


# Mesta z utežmi ~ prebivalstvo regije (za povprečno "nacionalno" vreme)
MESTA = {
    "Budimpešta": (47.50, 19.04, 0.45),
    "Debrecen":   (47.53, 21.63, 0.15),
    "Szeged":     (46.25, 20.15, 0.13),
    "Pécs":       (46.07, 18.23, 0.12),
    "Győr":       (47.68, 17.63, 0.15),
}
SPREMENLJIVKE = "temperature_2m,shortwave_radiation,wind_speed_100m,cloud_cover"


def prenesi_vreme() -> None:
    deli = []
    for ime, (lat, lon, w) in MESTA.items():
        print(f"  vreme: {ime}", flush=True)
        # zgodovina (arhiv ima ~5 dni zamika)
        zg = _get("https://archive-api.open-meteo.com/v1/archive", {
            "latitude": lat, "longitude": lon, "hourly": SPREMENLJIVKE,
            "start_date": ZACETEK.isoformat(),
            "end_date": (date.today() - timedelta(days=6)).isoformat(),
            "timezone": "UTC"})
        # zadnji dnevi + napoved 16 dni (zajame teden 47)
        np_ = _get("https://api.open-meteo.com/v1/forecast", {
            "latitude": lat, "longitude": lon, "hourly": SPREMENLJIVKE,
            "past_days": 10, "forecast_days": 16, "timezone": "UTC"})
        for js, vir in ((zg, "arhiv"), (np_, "napoved")):
            df = pd.DataFrame(js["hourly"])
            df["cas"] = pd.to_datetime(df.pop("time"), utc=True)
            df["mesto"], df["utez"], df["vir"] = ime, w, vir
            deli.append(df)

    vse = pd.concat(deli)
    # kjer se arhiv in napoved prekrivata, ima prednost arhiv (izmerjeno)
    vse = (vse.sort_values("vir").drop_duplicates(["cas", "mesto"], keep="first"))
    vse.to_parquet(DATA / "vreme_mesta.parquet")

    # tehtano nacionalno povprečje
    sp = SPREMENLJIVKE.split(",")
    nac = (vse.assign(**{s: vse[s] * vse["utez"] for s in sp})
              .groupby("cas")[sp].sum())
    nac["vir"] = vse.groupby("cas")["vir"].agg(lambda s: "napoved" if (s == "napoved").any() else "arhiv")
    nac.to_parquet(DATA / "vreme.parquet")
    print(f"  -> vreme: {len(nac):,} ur, {nac.index.min()} – {nac.index.max()}")


if __name__ == "__main__":
    print("Energy-Charts:")
    prenesi_energy_charts()
    print("Open-Meteo:")
    prenesi_vreme()
    print("Končano.")
