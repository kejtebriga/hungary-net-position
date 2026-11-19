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
.venv/bin/python src/podatki/prenos_podatkov.py
.venv/bin/python src/podatki/prenos_dodatno.py

# 2. preverjanje z uradnim virom ENTSO-E (potrebuje datoteko .env z vrstico ENTSOE_API_KEY=...)
.venv/bin/python src/podatki/prenos_entsoe.py
.venv/bin/python src/podatki/primerjava_virov.py

# 3. kontrola bilance in kontrolne vrednosti
.venv/bin/python src/podatki/preverjanje.py

# 4. analiza a) – grafi v figures/a/
.venv/bin/python src/analiza/analiza_a.py 1 2 3 4 5 6

# 5. napoved b) – test na vseh tednih + napoved tedna 47, grafi v figures/b/
.venv/bin/python src/modeli/napoved_b.py
```

Cena plina TTF: s strani Investing.com (*Historical Data → Download*) shrani CSV v `data/`.

## Struktura

```
src/podatki/   prenos podatkov in preverjanje (Energy-Charts, Open-Meteo, ENTSO-E)
src/analiza/   analiza a)
src/modeli/    napovedni modeli b)
figures/a, b, c   grafi po delih naloge
literatura/    povzetki člankov
report/        poročilo (LaTeX) in zamrznjena napoved tedna 47
```

## Grafi

Vsi grafi so v mapi `figures/` (PNG za ogled, PDF za poročilo). ✔ = v poročilu.

### a) Analiza (`figures/a/`)
| graf | kaj kaže | v poročilu |
|---|---|---|
| [a1a_letni_trend_brez_sonca](figures/a/a1a_letni_trend_brez_sonca.png) | proizvodnja brez sonca in poraba 2015–2026 + neto pozicija po letih | |
| [a1b_letni_trend_s_soncem](figures/a/a1b_letni_trend_s_soncem.png) | proizvodnja po vrstah elektrarn in poraba 2020–2026 | ✔ |
| [a2_meje_po_letih](figures/a/a2_meje_po_letih.png) | neto trgovanje po mejah, po letih | (kot tabela) |
| [a3a_mesecno_poraba_neto](figures/a/a3a_mesecno_poraba_neto.png) | poraba in neto pozicija po mesecih, tri obdobja | |
| [a3b_mesecno_viri_2022_2026](figures/a/a3b_mesecno_viri_2022_2026.png) | proizvodnja po vrstah in poraba po mesecih 2022–2026 | |
| [a4a_dnevni_profil_letni_casi](figures/a/a4a_dnevni_profil_letni_casi.png) | neto pozicija čez dan po letnih časih, tri obdobja | |
| [a4b_profil_okt_nov_po_letih](figures/a/a4b_profil_okt_nov_po_letih.png) | neto pozicija čez dan v oktobru in novembru, po letih | ✔ |
| [a5a_poraba_temperatura](figures/a/a5a_poraba_temperatura.png) | poraba proti temperaturi (ravna in zalomljena črta), tri obdobja | ✔ |
| [a5b_poraba_dnevi_v_tednu](figures/a/a5b_poraba_dnevi_v_tednu.png) | poraba po dnevih v tednu | |
| [a6_capture_price](figures/a/a6_capture_price.png) | baseload, peakload in vrednost (capture price) sonca, plina, Paksa | |

### b) Napoved neto pozicije (`figures/b/`)
| graf | kaj kaže | v poročilu |
|---|---|---|
| [b3_primerjava_modelov](figures/b/b3_primerjava_modelov.png) | napaka 18 modelov glede na naivni model, test 202 tednov | ✔ |
| [b1_napoved_t47_izbrani](figures/b/b1_napoved_t47_izbrani.png) | napoved tedna 47 po 15 minutah z razponom (izbrani model) | ✔ |
| [b1_napoved_t47](figures/b/b1_napoved_t47.png) | prva napoved tedna 47 (model po formuli, plin iz 2 tednov) | |
| [b2_test_tedni](figures/b/b2_test_tedni.png) | test prvega modela: dejansko proti napovedi po tednih 2025–2026 | |

### c) Cena (`figures/c/`)
| graf | kaj kaže | v poročilu |
|---|---|---|
| [c1_merit_order](figures/c/c1_merit_order.png) | cena/TTF proti preostali porabi (merit order) | ✔ |
| [c2_cene_po_dnevih](figures/c/c2_cene_po_dnevih.png) | dnevne cene tedna 45, 46 in napoved tedna 47 | |

## Opombe

- Vsi časi v podatkih so v UTC; za prikaz se pretvorijo v srednjeevropski čas.
- Predznaki: neto pozicija in meje so **+ = izvoz, − = uvoz** (Energy-Charts uporablja obratno konvencijo; pretvorba je v kodi).
- Napoved za teden 47 uporablja izključno podatke, znane do nedelje 15. 11. 2026, 23:45.

## Viri

### Podatki
- [Energy-Charts](https://www.energy-charts.info) (Fraunhofer ISE) – proizvodnja po vrstah elektrarn, poraba, čezmejno trgovanje, cene; na osnovi ENTSO-E
- [ENTSO-E Transparency Platform](https://transparency.entsoe.eu) – preverjanje podatkov, obvestila o razpoložljivosti elektrarne Paks
- [Open-Meteo](https://open-meteo.com) – temperatura in sončno sevanje (5 madžarskih mest), veter v severni Nemčiji; arhiv in napoved
- [Investing.com – Dutch TTF](https://www.investing.com/commodities/dutch-ttf-gas-c1-futures-historical-data) – cena plina
- [Electricity Maps – Grid Review 2025: Hungary](https://www.electricitymaps.com/grid-in-review-2025/hungary) – neodvisna kontrola letnih vrednosti

### Članki
- Lago, Marcjasz, De Schutter, Weron (2021): *Forecasting day-ahead electricity prices: A review of state-of-the-art algorithms, best practices and an open-access benchmark.* Applied Energy 293 – [arXiv:2008.08004](https://arxiv.org/abs/2008.08004)
- Jędrzejewski, Lago, Marcjasz, Weron (2022): *Electricity Price Forecasting: The Dawn of Machine Learning.* IEEE Power & Energy Magazine – [arXiv:2204.00883](https://arxiv.org/abs/2204.00883)
- Ghelasi, Ziel (2025): *A data-driven merit order: Learning a fundamental electricity price model.* Energy Economics – [arXiv:2501.02963](https://arxiv.org/abs/2501.02963)
- Stiewe, Xu, Eicke, Hirth (2024): *Cross-border cannibalization: spillover effects of wind and solar energy on interconnected European electricity markets* – [arXiv:2405.17166](https://arxiv.org/abs/2405.17166)
- *Where do Germany's electricity imports come from?* (2025) – [arXiv:2504.20232](https://arxiv.org/abs/2504.20232)
- Gulyás, Palkovics, Gondola (2024): *Analysis of Potential Energy Transition Schemes in Hungary: from Natural Gas to Electricity.* Chemical Engineering Transactions 114 – [PDF](https://cetjournal.it/cet/24/114/146.pdf)

Podrobnejši povzetki člankov: [literatura/povzetki_clankov.md](literatura/povzetki_clankov.md).
