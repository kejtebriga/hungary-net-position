# Povzetki člankov in virov (zapiski, ne za citiranje)

Izbrani so viri, ki so uporabni za nalogo (neto pozicija HU, napoved, cena).
Pri vsakem piše, **koliko sem ga prebrala** (cel članek / samo povzetek), da veš, kako trdna je vsebina.
Prebrano 18. 11. 2026.

---

## A. Kako napovedovati in kako preverjati napovedi

### 1. Electricity Price Forecasting: The Dawn of Machine Learning (2022)
Jędrzejewski, Lago, Marcjasz, Weron – IEEE Power & Energy Magazine. **Prebrano v celoti.**

- Pregled, kako so se modeli za napoved cen razvijali 25 let: od majhnih linearnih regresij → regresije z avtomatskim izborom spremenljivk (LASSO) → globoke nevronske mreže.
- **Najpomembnejša vhodna spremenljivka je napoved porabe** (dan vnaprej). Zanimivo: *dejanska* poraba ni boljša, ker trg ceno določi na podlagi napovedi.
- Odnos cena–poraba je **nelinearen** (»hokejska palica«: pri visoki porabi cena hitro naraste).
- Preprosti linearni modeli (LEAR) so zelo težko premagljivi; nevronske mreže so malo boljše, a do 100× računsko dražje.
- Proti naivni napovedi (»enako kot pred tednom, ista ura«) so dobri modeli boljši za 40–55 %.
- **Slabe prakse**: primerjati samo s šibkimi modeli; test na samo 4 tednih; »kontaminacija« (parametri izbrani na testnih podatkih).
- **Dobre prakse**: test vsaj 1 leto, test = zadnji del podatkov, primerjava z znanimi preprostimi modeli, več mer napake (tudi *relativni MAE* glede na naivno), modeli redno ponovno ocenjeni.

**Za nas:** naš test na 202 tednih in primerjava z naivno napovedjo je točno to, kar priporočajo. Napako lahko izrazimo kot *relativni MAE*: model po kosih 381 / naivna 578 ≈ **0,66** (34 % boljši od naivne). Za c): cena je nelinearno odvisna od porabe → graf cena–preostala poraba.

Povezava: https://arxiv.org/abs/2204.00883

### 2. Forecasting day-ahead electricity prices: review, best practices and an open-access benchmark (2021)
Lago, Marcjasz, De Schutter, Weron – Applied Energy 293. **Prebrana večina (metode, priporočila, rezultati).**

- Primerjava preprostega linearnega modela (LEAR) in nevronske mreže (DNN) na 5 trgih, vsak test 2 leti (104 tedne).
- Naivna primerjava: **cena pred 7 dnevi, ista ura**.
- Rezultat (relativni MAE, manj = bolje): DNN 0,40–0,60, LEAR 0,43–0,65 → oba precej boljša od naivne; DNN malo boljši.
- **Povprečje istega modela, ocenjenega na različno dolgih obdobjih** (8 tednov, 12 tednov, 3 leta, 4 leta), je bilo **vedno boljše** od najboljšega posameznega. Kratko obdobje ujame zadnje stanje, dolgo da stabilnost.
- Priporočila: modeli naj se ponovno ocenijo pogosto (pri njih dnevno); parametri se izberejo na ločenih podatkih, ne na testu; testi statistične pomembnosti razlik (Diebold-Mariano).

**Za nas:** (1) ideja **kombinacije** – npr. povprečje modelov z 2 tednoma, 3 dnevi in daljšim obdobjem; to je točno odgovor na vprašanje »plin iz zadnjih 3 dni ali iz 2 tednov« → oboje in povprečje. (2) Pri nas so se parametri ocenjevali enkrat na leto – lahko bi pogosteje.

Povezava: https://arxiv.org/abs/2008.08004

---

## B. Merit order in cena (za c)

### 3. A data-driven merit order: Learning a fundamental electricity price model (2025)
Ghelasi, Ziel – Energy Economics. **Samo povzetek.**

- Merit order (elektrarne razvrščene po strošku, cena = najdražja potrebna) – a parametre (izkoristki elektrarn, način ponujanja, razpoložljive moči) **ocenijo iz preteklih podatkov** namesto da jih predpostavijo.
- Ko dodajo **hidro, čezmejne tokove in popravek za nepopolno poročane moči**, je model bistveno boljši; na nemškem trgu je enako dober ali boljši od strojnega učenja, a je razložljiv (pove, katera tehnologija postavlja ceno).

**Za nas:** za c) potrjuje pristop z grafom »cena proti preostali porabi« – to je preprosta, iz podatkov ocenjena različica merit orderja. Za HU so **meje (uvoz)** del ponudbe, zato je cena HU tesno vezana na sosede.

Povezava: https://arxiv.org/abs/2501.02963

### 4. Cross-border cannibalization: spillover effects of wind and solar energy on interconnected European electricity markets (2024)
Stiewe, Xu, Eicke, Hirth. **Samo povzetek.**

- »Kanibalizacija« = več sonca/vetra → nižja cena ravno v urah, ko proizvajajo → nižja *capture price*.
- Podatki 30 evropskih območij 2015–2023: vrednost sonca in vetra pade **tudi zaradi sonca in vetra pri sosedih**, ne le doma.
- Boljše povezave ublažijo domači učinek, a okrepijo vpliv sosedov. Za sonce: +1 odstotna točka deleža (doma in pri sosedih) → vrednost sonca **−~4 odstotne točke**; za veter le ~−1.

**Za nas:** pojasni naš graf 6 (sonce 0,57 × baseload). Za c): **veter in sonce v Nemčiji/Avstriji znižata ceno na Madžarskem** (HU je močno povezana, ~50 % moči v povezavah) – zato v tabeli dejavnikov upoštevamo veter DE.

Povezava: https://arxiv.org/abs/2405.17166

### 5. Renewable cannibalisation explained (Montel, 2026 – blog)
**Prebrano v celoti (kratko).**

- Preprosta razlaga: sonce in veter imata skoraj ničelni strošek → izrineta plin iz merit orderja → cena pade, včasih negativna.
- *Capture price* = cena, tehtana s proizvodnjo (dejanski prihodek elektrarne), *baseload* = navadno povprečje.

**Za nas:** dober vir za preprosto razlago pojmov v poročilu/na razgovoru.

Povezava: https://montel.energy/resources/blog/renewable-cannibalisation-explained-why-more-solar-and-wind-can-reduce-captured-prices

---

## C. Meje in neto pozicija

### 6. Where do Germany's electricity imports come from? (2025)
**Samo povzetek.**

- Pri povezanem evropskem trgu ima **ekonomski smisel samo neto pozicija države**; trgovanje po posameznih mejah (*scheduled commercial exchanges*) ni dvostranski posel med akterji, ampak rezultat naknadnega izračuna algoritma.
- Od kod »prihaja« uvoz, je odvisno od izbrane metode.

**Za nas – pomembno opozorilo za del a):** številke po mejah (SK −1.100 MW, HR +335 MW …) beri previdno: kažejo smer trgovanja, ne »kdo komu prodaja«. Vsota (neto pozicija) pa je zanesljiva. To lahko v poročilu omeniš v enem stavku – pokaže razumevanje.

Povezava: https://arxiv.org/abs/2504.20232

---

## D. Madžarska

### 7. Analysis of Potential Energy Transition Schemes in Hungary: from Natural Gas to Electricity (2024)
Gulyás, Palkovics, Gondola – Chemical Engineering Transactions 114. **Prebrano v celoti.**

- Delež neto uvoza elektrike v porabi: **36 % (2014) → 30 % (2023)** (njihova definicija: brez lastne rabe elektrarn in izgub – zato višje od naših ~25 %).
- Madžarska je povezana z vsemi sosedi (Slovenija zadnja, 2023); **čezmejne povezave ≈ 50 % nameščene moči** (cilj EU je 15 %).
- Sonce: +2.600 MW v 2022–23, **~18–19 % proizvodnje**; cilj 12.000 MW do 2030. Plin v proizvodnji 2023: 20,5 % (7,17 TWh, najmanj od 2016).
- Načrti: **1.500 MW novih plinskih elektrarn**, **1 GW hranilnikov do 2030** (zdaj ~20 MW), 500–600 MW črpalne hidroelektrarne.
- Opozorilo: presežki sonca v konicah; **sezonsko shranjevanje ni rešeno** → pozimi uvoz.

**Za nas:** potrdi naše ugotovitve (sonce raste, plin pada, uvoz pozimi). Razlika 30 % vs naših ~25 % je samo v definiciji – dobro, da veš, če te vprašajo.

Povezava: https://cetjournal.it/cet/24/114/146.pdf

### 8. Electricity Grid Review 2025: Hungary (Electricity Maps)
**Prebrano v celoti (podatkovno poročilo).**

- 2025: **neto uvoz 9,14 TWh** (uvoz 22,0, izvoz 12,9 TWh). → Naš izračun iz trgovanja: **9,48 TWh** – dobro ujemanje (razlika zaradi metode).
- Uvoz neto: Slovaška 14,5 TWh, Avstrija 4,1 TWh; izvoz neto: Hrvaška 4,5, Romunija 3,6, Slovenija 2,1, Srbija 0,6 TWh → potrdi »tranzit sever → jug«.
- Proizvodnja: jedrska 45,6 %, plin 22,2 %, sonce 20,4 %, biomasa 4,9 %, premog 4,6 %, veter 1,7 %, hidro 0,6 %.
- Povprečna cena 112,4 €/MWh (naš izračun 2025: 108,5); **277 ur negativnih cen**; najvišja poraba 7,4 GW (20. 1. 2025).

**Za nas:** neodvisna kontrola naših številk iz dela a) – lahko omeniš kot »preverjeno z drugim virom«.

Povezava: https://www.electricitymaps.com/grid-in-review-2025/hungary

---

## E. Starejši, a idejno uporabni (samo za ideje)

- **Kombiniranje napovedi** – Nowotarski, Raviv, Trück, Weron (2014), Energy Economics: navadno **enakomerno povprečje** več napovedi je preprosto in močno; zapletene uteži se ne obnesejo bolje, razen če en model vedno zmaga. Povezava: https://ui.adsabs.harvard.edu/abs/2014EneEc..46..395N *(samo povzetek)*
- **Metoda podobnih dni** – Chen, Luh in sod. (2010), IEEE Trans. Power Systems: napoved porabe iz preteklih dni s podobnim vremenom in koledarjem; ključni korak je **dobra izbira podobnih dni**. Povezava: https://msl.engr.uconn.edu/paper/ChenYing/ChenYingShort-TermLoadForecasting_2010.pdf *(samo povzetek)*

## Ni bilo dostopno
- Hong, Pinson, Wang, Weron, Yang, Zareipour (2020), *Energy Forecasting: A Review and Outlook* – strežnik je zavrnil dostop (403). https://ideas.repec.org/p/ahh/wpaper/worms2008.html
