import re

import pandas as pd

MILES_TO_KM = 1.609344

df = pd.read_csv('data/epa/vehicles.csv', low_memory=False)
ev = df[df['atvType'] == 'EV'].copy()


NUM = r'\d+(?:\.\d+)?'
NAN = float('nan')
MIN_MOTOR_KW = 10  # menšie číslo je preklep v dátach ("1 and 242 kW")

# Autá, ktoré naozaj majú 3 alebo 4 motory. Pri ostatných zoznam s 3+ číslami
# ("140, 220 and 260 kW") znamená verzie modelu alebo výkon systému, nie motory.
TRUE_MULTI_MOTOR = re.compile(
    r'rivian|hummer|plaid|sapphire|folgore|nevera|lordstown|g 580', re.I)

# Počet motorov, ktorý vyplýva priamo z názvu modelu.
MOTORS_FROM_NAME = [
    (re.compile(r'\bquad\b|nevera|lordstown|g 580', re.I), 4),
    (re.compile(r'\btri\b|plaid|sapphire|gran(?:turismo|cabrio) folgore', re.I), 3),
]

# Ručné opravy zápisov, ktoré sa z textu správne prečítať nedajú:
# (výrobca, regex na model, čísla z evMotor alebo None = akékoľvek, hodnota).
# Hodnota je zoznam výkonov jednotlivých motorov, alebo (výkon systému, počet motorov),
# keď rozdelenie na motory nepoznáme.
MANUAL_FIXES = [
    # Ford pri Mach-E AWD píše výkon celého systému dvakrát. AWD má 266 hp = 198 kW
    # (rovnako ako RWD), AWD Extended 346 hp = 258 kW (roky 2025-26 uvádzajú "258 kW").
    ('Ford', r'mach-e', ('198', '198'), (198, 2)),
    ('Ford', r'mach-e', ('209', '209'), (258, 2)),
    ('Ford', r'mach-e', ('258', '258'), (258, 2)),
    # F-150 Lightning SR by mal viac než silnejšia verzia ER ("210 and 210").
    # Ford uvádza 452 hp = 337 kW.
    ('Ford', r'f-150', ('358', '358'), (337, 2)),
    # VinFast "260 and 300" sú výkony verzií Eco a Plus, nie dvoch motorov. Rozdelenie
    # na motory je z tých istých modelov z roku 2023 ("130 and 130", "150 and 150").
    ('Vinfast', r'\beco\b', ('260', '300'), [130, 130]),
    ('Vinfast', r'\bplus\b', ('260', '300'), [150, 150]),
    # Mercedes G 580 má 4 motory po 108 kW, EPA podľa roku uvádza 3, 1 alebo iné číslo.
    ('Mercedes-Benz', r'g 580', None, [108, 108, 108, 108]),
]


def motor_numbers(text):
    """Vytiahne z textu evMotor čísla výkonov motorov (kW) ako reťazce.

    "127 and 200 kW PMSM"                             -> ['127', '200']
    "193 (front) 375 (rear) (100 kW-hr battery pack)" -> ['193', '375']
    "160 and 160 AC 3-phase"                          -> ['160', '160']
    "193 (front), 205/375 (rear) kW ACPM"             -> ['193', '205/375']
    "TBD"                                             -> []
    """
    if not isinstance(text, str):
        return []
    s = text.lower()
    s = re.sub(rf'\(\s*{NUM}\s*kw-hr[^)]*\)', ' ', s)  # kapacita batérie, nie motor
    s = re.sub(r'\d+-phase', ' ', s)                   # "3-Phase" nie je výkon
    s = s.split('kw')[0]                               # čísla za "kW" nás nezaujímajú
    # "205/375" = dve alternatívne verzie toho istého motora -> jeden token
    return re.findall(rf'{NUM}(?:/{NUM})*', s)


def motors_from_name(name):
    """Počet motorov podľa názvu modelu ("Rivian R1T Quad Max" -> 4), inak None."""
    for pattern, n in MOTORS_FROM_NAME:
        if pattern.search(name):
            return n
    return None


def manual_fix(row, tokens):
    """Vráti ručnú opravu z MANUAL_FIXES pre daný riadok, inak None."""
    for make, model_re, key, value in MANUAL_FIXES:
        if (row['make'] == make and re.search(model_re, row['model'], re.I)
                and (key is None or tuple(tokens) == key)):
            return value
    return None


def parse_motor(row):
    """Vráti (výkon motorov v kW, počet motorov, výkony jednotlivých motorov, zdroj).

    Zdroj: 'text' = spočítané z evMotor, 'oprava' = ručná oprava, 'nezname' = nevieme,
    'doplnit' = text neuvádza všetky motory, výkon sa dohľadá v inom roku.
    """
    tokens = motor_numbers(row['evMotor'])
    fix = manual_fix(row, tokens)
    if isinstance(fix, tuple):
        return fix[0], fix[1], None, 'oprava'
    if fix is not None:
        return sum(fix), len(fix), tuple(fix), 'oprava'
    if not tokens:
        return NAN, NAN, None, 'nezname'

    awd = isinstance(row['drive'], str) and ('4-Wheel' in row['drive'] or 'All-Wheel' in row['drive'])
    name = f"{row['make']} {row['model']}"
    named = motors_from_name(name)
    vals = [float(v) for t in tokens for v in t.split('/')]
    if min(vals) < MIN_MOTOR_KW:
        return NAN, named or (2 if awd else 1), None, 'nezname'  # preklep v dátach

    if not awd:
        # Pohon jednej nápravy = 1 motor. "228 and 243 kW" pri RWD sú dve verzie
        # toho istého motora -> berieme vyšší výkon.
        return max(vals), 1, None, 'text'

    if any('/' in t for t in tokens):
        return NAN, named or len(tokens), None, 'nezname'       # nevieme, ktorá verzia
    if len(tokens) >= 3 and not TRUE_MULTI_MOTOR.search(name):
        return NAN, 2, None, 'nezname'                          # verzie modelu, nie motory
    motors = tuple(float(t) for t in tokens)
    if len(motors) == 1 or (named and len(motors) != named):
        # AWD má aspoň 2 motory, takže text ich neuvádza všetky. Jedno číslo býva výkon
        # jedného motora, nie celého auta (Kia EV9 AWD: 2025 "141 and 141", 2026 "141 kW").
        return NAN, named or 2, motors, 'doplnit'
    return sum(motors), len(motors), motors, 'text'


def base_model(model):
    """Názov modelu bez veľkosti kolies a označenia AWD, aby sa dali porovnať
    rovnaké autá z rôznych rokov: "R1S 21 inch Dual Large" -> "r1s dual large"."""
    s = re.sub(r'\(.*?\)', ' ', model.lower())
    s = re.sub(r'\b\d+(?:/\d+)?\s*-?\s*in(?:ch)?\b(?:\s+wheels?)?', ' ', s)
    s = re.sub(r'\b(?:awd|4wd)\b', ' ', s)
    return ' '.join(s.split())


def same_car(row, donor):
    """True, ak čísla z neúplného zápisu sedia s autom z iného roku: buď je jedno
    číslo výkon celého systému, alebo sú uvedené motory medzi motormi toho auta."""
    motors = row['motor_list']
    if len(motors) == 1 and motors[0] == donor['motor_kw']:
        return True
    rest = list(donor['motor_list']) if isinstance(donor['motor_list'], tuple) else []
    for v in motors:
        if v not in rest:
            return False
        rest.remove(v)
    return True


def fill_from_other_years(ev):
    """Doplní výkon riadkov so zdrojom 'doplnit' z toho istého modelu z najbližšieho
    roku. Keď sa taký model nenájde, výkon zostane NaN."""
    donors = ev[ev['motor_src'].isin(['text', 'oprava']) & (ev['n_motors'] >= 2)]
    for idx in ev.index[ev['motor_src'] == 'doplnit']:
        row = ev.loc[idx]
        named = motors_from_name(f"{row['make']} {row['model']}")
        cand = donors[(donors['make'] == row['make']) & (donors['model_base'] == row['model_base'])]
        found = [i for i, d in cand.iterrows()
                 if same_car(row, d) and (named is None or d['n_motors'] == named)]
        if found:
            best = cand.loc[min(found, key=lambda i: abs(cand.at[i, 'year'] - row['year']))]
            ev.loc[idx, ['motor_kw', 'n_motors', 'motor_src']] = [best['motor_kw'], best['n_motors'], 'iny rok']
        else:
            ev.loc[idx, 'motor_src'] = 'nezname'


parsed = pd.DataFrame(ev.apply(parse_motor, axis=1).tolist(), index=ev.index,
                      columns=['motor_kw', 'n_motors', 'motor_list', 'motor_src'])
ev = ev.join(parsed)
ev['model_base'] = ev['model'].map(base_model)
fill_from_other_years(ev)
ev['n_motors'] = ev['n_motors'].astype('Int64')
ev['charge240'] = ev['charge240'].replace(0, float('nan'))  # 0 = údaj chýba
ev['range_km'] =(ev['range'] * MILES_TO_KM).round()
ev['kwh_per_100km'] = (ev['combE'] / MILES_TO_KM).round(2)

clean = ev.rename(columns={
    'VClass': 'vehicle_class',
    'charge240': 'charge_time_240v_hr',
})[[
    'year', 'make', 'model', 'vehicle_class', 'drive',
    'motor_kw', 'n_motors', 'charge_time_240v_hr', 'kwh_per_100km', 'range_km',
]]

clean.to_csv('data/ev_epa.csv', index=False)
print(clean.shape)
print(ev['motor_src'].value_counts().to_string())  # odkiaľ je motor_kw