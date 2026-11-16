# Neto pozicija madžarskega elektroenergetskega sistema

Analiza neto pozicije Madžarske (proizvodnja − poraba = izvoz − uvoz):

- **a)** razčlenitev neto pozicije: viri proizvodnje, dejavniki porabe, meje, spremembe skozi čas
- **b)** napoved neto pozicije za teden 47 (16.–22. 11. 2026) z razponom
- **c)** smer povprečne dan-vnaprej cene v tednu 47 glede na teden 45 (290,98 €/MWh)

## Viri podatkov

| Vir | Kaj | Dostop |
|---|---|---|
| [Energy-Charts](https://www.energy-charts.info) (Fraunhofer ISE, podatki iz ENTSO-E) | proizvodnja po virih, poraba, čezmejno trgovanje, cene, nameščena moč | javni API, brez ključa |
| [ENTSO-E Transparency Platform](https://transparency.entsoe.eu) | iste količine iz uradnega vira – za preverjanje | API ključ (brezplačna registracija) |
| [Open-Meteo](https://open-meteo.com) | temperatura, sončno sevanje, veter (zgodovina + napoved) | javni API, brez ključa |
| [Investing.com](https://www.investing.com/commodities/dutch-ttf-gas-c1-futures-historical-data) | cena plina TTF (front month) | ročni prenos CSV |

Mapa `data/` ni v repozitoriju; ustvarijo jo spodnje skripte.

## Zagon

```bash
python3 -m venv .venv
.venv/bin/pip install pandas pyarrow matplotlib requests scikit-learn

# 1. prenos podatkov (Energy-Charts + Open-Meteo); ~30 min zaradi omejitev hitrosti API-ja
.venv/bin/python src/prenos_podatkov.py
.venv/bin/python src/prenos_dodatno.py

# 2. preverjanje z uradnim virom ENTSO-E (potrebuje datoteko .env z vrstico ENTSOE_API_KEY=...)
.venv/bin/python src/prenos_entsoe.py
.venv/bin/python src/primerjava_virov.py

# 3. kontrola bilance in kontrolne vrednosti
.venv/bin/python src/preverjanje.py
```

Cena plina TTF: s strani Investing.com (*Historical Data → Download*) shrani CSV v `data/`.

## Struktura

```
src/        skripte za prenos, preverjanje in analizo
figures/    grafi
report/     poročilo (LaTeX)
```

## Opombe

- Vsi časi v podatkih so v UTC; za prikaz se pretvorijo v srednjeevropski čas.
- Predznaki: neto pozicija in meje so **+ = izvoz, − = uvoz** (Energy-Charts uporablja obratno konvencijo; pretvorba je v kodi).
- Napoved za teden 47 uporablja izključno podatke, znane do nedelje 15. 11. 2026, 23:45.
