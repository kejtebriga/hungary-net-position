"""
Prenos podatkov NEPOSREDNO z ENTSO-E Transparency Platform (uradni vir), za preverjanje
podatkov Energy-Charts. Rezultat gre v ločeno mapo data/entsoe/.

Nabori (Madžarska, ponudbeno območje 10YHU-MAVIR----U):
  - A44  dan-vnaprej cene                               -> cena.parquet          [EUR/MWh]
  - A65  dejanska poraba (processType A16)              -> poraba.parquet        [MW]
  - A75  dejanska proizvodnja po virih (A16)            -> proizvodnja.parquet   [MW]
  - A09  dogovorjene čezmejne izmenjave (skupaj, A05)   -> izmenjave.parquet     [MW, + = uvoz v HU]
  - A11  fizični čezmejni tokovi                        -> fizicni_tokovi.parquet[MW, + = uvoz v HU]

API ključ se prebere iz datoteke .env (ENTSOE_API_KEY=...), nikoli se ne izpiše.
Zagon: .venv/bin/python src/prenos_entsoe.py
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

KOREN = Path(__file__).resolve().parents[1]
IZHOD = KOREN / "data" / "entsoe"
KOSI = IZHOD / "kosi"
KOSI.mkdir(parents=True, exist_ok=True)

API = "https://web-api.tp.entsoe.eu/api"
HU = "10YHU-MAVIR----U"
SOSEDI = {
    "AT": "10YAT-APG------L", "SK": "10YSK-SEPS-----K", "RO": "10YRO-TEL------P",
    "HR": "10YHR-HEP------M", "RS": "10YCS-SERBIATSOV", "SI": "10YSI-ELES-----O",
    "UA": "10Y1001C--00003F",
}
VIRI = {  # ENTSO-E psrType -> ime (enako kot v Energy-Charts, za lažjo primerjavo)
    "B01": "Biomass", "B02": "Fossil brown coal / lignite", "B04": "Fossil gas",
    "B05": "Fossil hard coal", "B06": "Fossil oil", "B09": "Geothermal",
    "B10": "Hydro pumped storage", "B11": "Hydro Run-of-River", "B12": "Hydro water reservoir",
    "B14": "Nuclear", "B15": "Other renewables", "B16": "Solar", "B17": "Waste",
    "B19": "Wind onshore", "B20": "Others",
}

ZACETEK = datetime(2025, 11, 1, tzinfo=timezone.utc) - timedelta(hours=1)  # 1. 11. 2025 00:00 CET
KONEC = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(days=2)


def _kljuc() -> str:
    for vr in (KOREN / ".env").read_text(encoding="utf-8").splitlines():
        if vr.startswith("ENTSOE_API_KEY="):
            return vr.split("=", 1)[1].strip()
    raise SystemExit("V .env ni ENTSOE_API_KEY.")


KLJUC = _kljuc()
seja = requests.Session()


def _get(params: dict) -> str | None:
    """Vrne XML ali None, če podatkov ni. Ključ se ne pojavi v nobenem izpisu."""
    for i in range(5):
        try:
            r = seja.get(API, params={"securityToken": KLJUC, **params}, timeout=120)
        except requests.exceptions.RequestException as e:
            print(f"    ponovni poskus {i + 1}/5 ({type(e).__name__})", flush=True)
            time.sleep(10 * (i + 1))
            continue
        if r.status_code == 200:
            return r.text
        if "No matching data" in r.text or "<code>999</code>" in r.text:
            return None
        print(f"    ponovni poskus {i + 1}/5 (HTTP {r.status_code})", flush=True)
        time.sleep(10 * (i + 1))
    print("    !! zahtevek ni uspel", flush=True)
    return None


def _razcleni(xml: str, vrednost: str) -> list[tuple[dict, pd.Series]]:
    """
    Razčleni ENTSO-E XML v (atributi, časovna vrsta). Upošteva stisnjen zapis (curveType A03):
    manjkajoče pozicije pomenijo 'enako kot prejšnja vrednost'.
    """
    koren = ET.fromstring(xml)
    for el in koren.iter():  # odstrani imenske prostore
        el.tag = el.tag.split("}", 1)[-1]
    rezultat = []
    for ts in koren.iter("TimeSeries"):
        atr = {c.tag: (c.text or "").strip() for c in ts if len(c) == 0}
        psr = ts.find("MktPSRType/psrType")
        if psr is not None:
            atr["psrType"] = psr.text
        for per in ts.iter("Period"):
            zac = pd.Timestamp(per.find("timeInterval/start").text)
            kon = pd.Timestamp(per.find("timeInterval/end").text)
            res = pd.Timedelta(per.find("resolution").text.replace("PT", "").lower()
                               .replace("m", "min"))
            n = int((kon - zac) / res)
            vr = pd.Series(index=range(1, n + 1), dtype=float)
            for pt in per.iter("Point"):
                vr[int(pt.find("position").text)] = float(pt.find(vrednost).text)
            vr = vr.ffill()
            vr.index = pd.date_range(zac, periods=n, freq=res)
            rezultat.append((atr, vr))
    return rezultat


def _meseci():
    d = ZACETEK
    while d < KONEC:
        nasl = min((d + timedelta(days=32)).replace(day=1, hour=d.hour), KONEC)
        yield d, nasl
        d = nasl


def _f(t: datetime) -> str:
    return t.strftime("%Y%m%d%H%M")


def _letno():
    """Največ eno leto na zahtevek (dovoljeno za čezmejne podatke) – veliko manj zahtevkov."""
    d = ZACETEK
    while d < KONEC:
        nasl = min(d + timedelta(days=365), KONEC)
        yield d, nasl
        d = nasl


def _zberi(ime: str, params_fn, pretvori, obdobja=None) -> pd.DataFrame:
    deli = []
    obd = list(obdobja() if obdobja else _meseci())
    for n, (zac, kon) in enumerate(obd):
        pot = KOSI / f"{ime}_{zac:%Y-%m}.parquet"
        if pot.exists() and n < len(obd) - 1:
            deli.append(pd.read_parquet(pot))
            continue
        xml = _get({**params_fn(), "periodStart": _f(zac), "periodEnd": _f(kon)})
        df = pretvori(xml) if xml else pd.DataFrame()
        df.to_parquet(pot)
        deli.append(df)
        time.sleep(0.5)
    out = pd.concat(deli).sort_index()
    return out[~out.index.duplicated(keep="last")]


def cena():
    def pretvori(xml):
        vrste = [v for a, v in _razcleni(xml, "price.amount")]
        return pd.concat(vrste).to_frame("cena") if vrste else pd.DataFrame()
    return _zberi("cena", lambda: {"documentType": "A44", "in_Domain": HU, "out_Domain": HU},
                  pretvori)


def poraba():
    def pretvori(xml):
        vrste = [v for a, v in _razcleni(xml, "quantity")]
        return pd.concat(vrste).to_frame("Load") if vrste else pd.DataFrame()
    return _zberi("poraba", lambda: {"documentType": "A65", "processType": "A16",
                                     "outBiddingZone_Domain": HU}, pretvori)


def proizvodnja():
    def pretvori(xml):
        stolpci = {}
        for a, v in _razcleni(xml, "quantity"):
            if "outBiddingZone_Domain.mRID" in a:  # poraba črpalnih elektrarn – izpustimo
                continue
            ime = VIRI.get(a.get("psrType"), a.get("psrType"))
            stolpci[ime] = pd.concat([stolpci[ime], v]) if ime in stolpci else v
        return pd.DataFrame(stolpci)
    return _zberi("proizvodnja", lambda: {"documentType": "A75", "processType": "A16",
                                          "in_Domain": HU}, pretvori)


def cezmejno(doc: str, ime: str, dodatno: dict) -> pd.DataFrame:
    """Neto uvoz po mejah: (sosed -> HU) − (HU -> sosed)."""
    stolpci = {}
    for drz, eic in SOSEDI.items():
        def smer(iz, v):
            def pretvori(xml):
                vrste = [s for a, s in _razcleni(xml, "quantity")]
                if not vrste:
                    return pd.DataFrame()
                s = pd.concat(vrste)
                s = s.groupby(level=0).sum()
                return s.to_frame("v")
            return _zberi(f"{ime}_{drz}_{'uvoz' if v == HU else 'izvoz'}_leto",
                          lambda: {"documentType": doc, "in_Domain": v, "out_Domain": iz, **dodatno},
                          pretvori, obdobja=_letno)
        uvoz, izvoz = smer(eic, HU), smer(HU, eic)
        if uvoz.empty and izvoz.empty:
            print(f"    {drz}: ni podatkov", flush=True)
            continue
        # poenotimo na urno ločljivost, ker smeri imajo lahko različno ločljivost
        u = uvoz["v"].resample("h").mean() if not uvoz.empty else 0
        i = izvoz["v"].resample("h").mean() if not izvoz.empty else 0
        stolpci[drz] = (u - i) if not (isinstance(u, int) and isinstance(i, int)) else None
    df = pd.DataFrame(stolpci)
    df["sum"] = df.sum(axis=1, min_count=1)
    return df


if __name__ == "__main__":
    import sys
    koraki = {
        "cena": cena,
        "poraba": poraba,
        "proizvodnja": proizvodnja,
        "izmenjave": lambda: cezmejno("A09", "izmenjave", {"contract_MarketAgreement.Type": "A05"}),
        "fizicni_tokovi": lambda: cezmejno("A11", "fizicni", {}),
    }
    izbrani = sys.argv[1:] or list(koraki)  # npr.: python src/prenos_entsoe.py izmenjave fizicni_tokovi
    for ime, fn in koraki.items():
        if ime not in izbrani:
            continue
        print(f"{ime} ...", flush=True)
        try:
            df = fn()
            df.to_parquet(IZHOD / f"{ime}.parquet")
            print(f"  -> {ime}: {len(df):,} vrstic, {df.index.min()} – {df.index.max()}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"!! {ime} ni uspel: {type(e).__name__}: {e}", flush=True)
    print("Končano.")
