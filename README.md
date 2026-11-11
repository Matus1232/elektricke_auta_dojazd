# Predikcia dojazdu elektrických áut

Model strojového učenia, ktorý z technických parametrov elektrického auta predpovedá jeho dojazd v km.

**Výsledok:** vyladený Gradient Boosting sa na testovacích dátach mýli v priemere o **15,5 km** (MAE)
a vysvetlí **93 %** rozptylu dojazdu (R² = 0,93). Pre typické auto je chyba iba ~5 km.

## Dáta

Databáza amerického úradu EPA ([fueleconomy.gov](https://www.fueleconomy.gov/feg/download.shtml)),
1585 elektrických áut z rokov 2011–2027.

**Príznaky:** rok, značka, trieda vozidla, pohon, výkon motora, počet motorov, čas nabíjania (240 V)
a spotreba. **Cieľ:** dojazd `range_km`.

## Postup

| Krok | Súbor | Čo robí |
|---|---|---|
| 1 | `priprav_epa.py` | vyberie z EPA dát elektrické autá, z textu vytiahne výkon a počet motorov, prevedie jednotky na km |
| 2 | `analyza.ipynb` | analýza a čistenie dát, uloží `data/ev_clean.csv` |
| 3 | `preprocessing.ipynb` | rozdelenie na tréning a test (80/20), one-hot encoding a škálovanie |
| 4 | `modely.ipynb` | porovnanie modelov krížovou validáciou (baseline, Ridge, Random Forest, Gradient Boosting) |
| 5 | `ladenie.ipynb` | ladenie hyperparametrov cez `GridSearchCV` |
| 6 | `vyhodnotenie.ipynb` | finálny test, rozbor chýb a dôležitosť príznakov |

## Spustenie

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Súbory `data/ev_epa.csv` a `data/ev_clean.csv` sú v repozitári, notebooky sa preto dajú spustiť hneď.
Na znovuvytvorenie `ev_epa.csv` stiahni
[vehicles.csv.zip](https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip), rozbaľ ho do `data/epa/`
a spusti `python priprav_epa.py`.

## Obmedzenia

V dátach chýba kapacita batérie. Model ju odhaduje z času nabíjania, ten však závisí aj od výkonu
nabíjačky. Najväčšie chyby preto vznikajú pri autách, kde čas nabíjania nezodpovedá veľkosti batérie
(napr. Chevrolet Silverado EV, rôzne batérie Tesla Model S).
