# WasteLog

Gestione formulari di trasporto rifiuti — desktop app.

## Funzionalità

- **Inserimento** — registra ogni bustina con Produttore, Unità Locale (Città + Indirizzo), Codice ERR, Destinatario e Peso.
- **Schede RIF** — visualizza i record raggruppati per Codice ERR, con totale per scheda.
- **Riepilogo** — somme aggregate per Produttore, per Unità Locale e peso totale generale.
- Dati salvati localmente in SQLite (`wastelog.db`).

## Avvio rapido

```bash
pip install PyQt6
python main.py
```

## Build eseguibile (Windows / Linux / macOS)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name WasteLog main.py
# l'eseguibile si trova in dist/
```
