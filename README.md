# WasteLog

A desktop application for managing waste transport forms (formulari rifiuti).
Track every shipment by producer, local unit, waste code (ERR), recipient, and weight — all stored locally, no internet connection required.

## Features

- **Inserimento** — log each record with Producer, Local Unit, ERR Code, Recipient, and Weight.
- **Schede RIF** — view records grouped by ERR Code, with a total weight per card.
- **Riepilogo** — aggregated totals split across three side-by-side tables:
  - *Per Produttore e Unità Locale* — weight per producer + local unit, with a progressive RT column (RT1, RT2, …) assigned in insertion order.
  - *Per Codice ERR* — weight ranked by ERR code.
  - *Per Destinazione* — weight ranked by recipient/destination.
- Overall total weight displayed at the top of the summary page.
- Data is saved locally in a SQLite database (`wastelog.db`) — nothing leaves your machine.
- **Auto-update** — on launch, WasteLog checks GitHub for a newer release. If one is available, a download button appears in the sidebar. Click it to replace the executable in-place automatically.

## Download (Windows)

Go to the [Releases](../../releases/latest) page and download `WasteLog.exe`.  
Open it directly — no installation required.

> **Note:** Windows may show a SmartScreen warning on first launch. Click **More info → Run anyway** to proceed.
