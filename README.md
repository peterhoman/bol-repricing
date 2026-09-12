# Bol.com Automatische Repricing Tool

Automatisch monitoren van concurrentprijzen en aanpassen van je Bol.com prijzen voor koopblok (#1).

## Setup

### 1. Environment
```bash
cd bol-repricing
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Credentials
```bash
copy .env.example .env
```

Edit `.env` en vul in:
- `BOL_CLIENT_ID`: Van je Bol.com account → API
- `BOL_CLIENT_SECRET`: Van je Bol.com account → API

### 3. Run Fase 1
```bash
python src/main.py
```

Dit:
- ✅ Haalt alle ~3000 producten op
- ✅ Slaat ze in SQLite database op
- ✅ Haalt concurrentprijzen op
- ✅ Bereken minimumprijs per artikel

## Database

`bol_repricing.db` bevat:
- **products**: EAN, SKU, titel, prijs, minimumprijs
- **competitors**: Concurrentprijzen per product
- **price_changes**: Log van alle prijswijzigingen

## Prijsberekening

**Normale prijs** (Channable):
```
if klantprijs < €10:
    (klantprijs + 1) × 2.6 + 8.5
else:
    klantprijs × 2.6 + 8.5
```

**Minimumprijs** (tool mag hier niet onder):
```
klantprijs × 1.9 + 8.5
```

## Phases

- **Fase 1** ✅: Data ophalen + database
- **Fase 2**: Dashboard (koopblok status per artikel)
- **Fase 3**: Automatische repricing (kat-en-muis met concurrenten)

## Status

🚀 Fase 1 klaar om te testen!
