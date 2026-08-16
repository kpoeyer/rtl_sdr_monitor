# 📡 RTL-SDR Multi-Protocol Monitor

Web-based GUI voor het monitoren van meerdere radio-protocollen met een RTL-SDR ontvanger op Linux.

## Ondersteunde protocollen

| Protocol | Frequentie | Omschrijving |
|----------|-----------|--------------|
| ✈ **ADS-B** | 1090 MHz | Vliegtuig tracking (dump1090) |
| 🚢 **AIS** | 161.975 / 162.025 MHz | Scheepvaart tracking |
| 📝 **ACARS** | 131.550 MHz | Vliegtuig communicatie |
| 🚨 **P2000** | 169.650 MHz | Nederlandse hulpdiensten |
| 📟 **POCSAG** | 169.650 MHz | Semafoon netwerk |
| 📡 **ERMES** | 169.450 MHz | Europees semafoonsysteem |

## Installatie

### 1. Vereisten

```bash
# RTL-SDR drivers en tools
sudo apt-get install rtl-sdr librtlsdr-dev

# Decoders
sudo apt-get install dump1090-mutability   # of: readsb
sudo apt-get install multimon-ng           # POCSAG / P2000
sudo apt-get install aisdecoder            # AIS (of rtl-ais)
sudo apt-get install acarsdec              # ACARS
```

### 2. Python omgeving

```bash
cd rtl_sdr_monitor
pip install -r requirements.txt
```

### 3. Starten

```bash
# Met simulatie (geen hardware nodig)
python main.py

# Met echte SDR hardware
python main.py --no-sim

# Andere poort
python main.py --port 8080
```

Open vervolgens **http://localhost:5000** in je browser.

## Features

- ✅ **Real-time berichten** - Live feed van alle gedecodeerde berichten
- ✅ **Interactieve kaart** - Bekijk vliegtuigen, schepen en incidenten op een kaart (Leaflet/OpenStreetMap)
- ✅ **Per-protocol filters** - Tabbladen om per protocol te filteren
- ✅ **Simulatie modus** - Werkt zonder SDR-hardware voor testen en demonstratie
- ✅ **Configuratie panel** - Frequenties en instellingen aanpasbaar via de UI
- ✅ **Donker thema** - Professionele dark-mode interface
- ✅ **Live status** - LED-indicatoren per decoder

## Schermen

- **Berichten overzicht** - Alle binnenkomende berichten in chronologische volgorde
- **Kaart weergave** - Locatie van vliegtuigen, schepen en incidenten
- **Configuratie** - Frequenties, gain, PPM en kaartinstellingen

## Architectuur

```
rtl_sdr_monitor/
├── main.py              # Flask + SocketIO server
├── decoders.py          # Decoder processen en simulator
├── config.json          # Configuratie bestand
├── requirements.txt     # Python dependencies
├── templates/
│   └── index.html       # Web interface
└── static/
    ├── css/style.css    # Dark theme styling
    └── js/
        ├── app.js       # SocketIO client + UI logic
        └── map.js       # Leaflet map module
```

## Echte SDR gebruiken

Wanneer je de simulatie uitschakelt (`--no-sim`), start de applicatie de volgende processen:

- **ADS-B**: `dump1090 --net --net-ro-size 500 --net-ro-rate 5 --aggressive --interactive`
- **ACARS**: `acarsdec -o 2 -r 0 <freqs>`
- **AIS**: `rtl_ais -n 8100` of `rtl_fm ... | aisdecoder`
- **POCSAG/P2000**: `rtl_fm -f 169.65M -M fm -s 22050 | multimon-ng -t raw -a POCSAG -`
- **ERMES**: `rtl_fm -f 169.45M -M fm -s 12500 | multimon-ng -t raw -a ERMES -`

Pas de commando's en frequenties aan in `config.json` of via het configuratiepaneel in de web UI.

## Locatie

Standaard staat de kaart gecentreerd op **Noord-Brabant / Fijnaart** (51.636, 4.471).
Pas dit aan in het configuratiepaneel onder "Kaart".