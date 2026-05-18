#!/usr/bin/env python3
"""
main.py
-------
Punto di ingresso e interfaccia grafica dell'applicazione WasteLog.

ARCHITETTURA GENERALE
=====================
L'app segue il pattern MVC semplificato:
  - Model  → database.py  (dati e logica di business)
  - View   → le classi Widget qui sotto (cosa vede l'utente)
  - Controller → MainWindow (coordina i widget e gestisce gli eventi)

STRUTTURA DEI WIDGET (albero gerarchico)
========================================
MainWindow (QMainWindow)
  └── root (QWidget)                ← widget centrale della finestra
       ├── Sidebar (QFrame)         ← colonna sinistra scura, navigazione
       └── right (QWidget)          ← area destra, cambia contenuto
            ├── hdr_frame (QFrame)  ← barra titolo in cima
            └── stack (QStackedWidget)  ← mostra UNA pagina alla volta
                 ├── FormPage       ← inserimento nuovi record
                 ├── RifPage        ← schede RIF per codice ERR
                 └── SummaryPage    ← riepilogo aggregato

FLUSSO DEI DATI
===============
1. L'utente compila il form in FormPage e clicca "Aggiungi".
2. FormPage chiama db.insert() → i dati vanno nel database SQLite.
3. FormPage emette il segnale record_added.
4. MainWindow riceve il segnale e, se la pagina corrente è RifPage
   o SummaryPage, chiama refresh() per aggiornare la vista.
"""

import sys
import os
import json
import subprocess
import tempfile
import webbrowser
import urllib.request
import urllib.error

# ── Importazioni Qt ──────────────────────────────────────────────────────────
# PyQt6 è il binding Python per il framework Qt (C++).
# Qt gestisce finestre, pulsanti, tabelle, layout, eventi, ecc.
from PyQt6.QtWidgets import (
    QApplication,       # oggetto principale: gestisce il ciclo eventi
    QMainWindow,        # finestra principale con barra del titolo
    QWidget,            # widget di base (contenitore generico)
    QFrame,             # come QWidget ma con bordo opzionale
    QLabel,             # testo non modificabile
    QPushButton,        # pulsante cliccabile
    QLineEdit,          # campo di testo a riga singola
    QTableWidget,       # tabella con celle editabili
    QTableWidgetItem,   # singola cella della tabella
    QHeaderView,        # intestazione riga/colonna della tabella
    QScrollArea,        # area con scroll automatico
    QVBoxLayout,        # disposizione verticale dei widget figli
    QHBoxLayout,        # disposizione orizzontale dei widget figli
    QGridLayout,        # disposizione a griglia (righe × colonne)
    QStackedWidget,     # contenitore che mostra un solo figlio alla volta
    QAbstractItemView,  # classe base per le viste di dati (tabelle, ecc.)
    QMessageBox,        # finestre di dialogo (conferma, errore, ecc.)
)
from PyQt6.QtCore import (
    Qt,           # costanti Qt (allineamento, cursori, orientazione, ecc.)
    pyqtSignal,   # per definire segnali personalizzati tra widget
    QThread,      # thread Qt integrato nel ciclo eventi
)
from PyQt6.QtGui import QFont  # (importato per futuri usi tipografici)

from database import Database  # il nostro livello dati

VERSION      = "1.0.3"
GITHUB_OWNER = "chriisey"
GITHUB_REPO  = "WasteLog"


# ═══════════════════════════════════════════════════════════════════════════════
# STYLESHEET (QSS)
# ═══════════════════════════════════════════════════════════════════════════════
"""
QSS (Qt Style Sheets) funziona come i CSS del web.
Ogni regola ha un selettore (es. QPushButton#add_btn) e delle proprietà.

Selettori usati:
  QFrame#sidebar       → seleziona il QFrame con objectName="sidebar"
  QPushButton#nav_btn  → seleziona i pulsanti di navigazione
  QPushButton#nav_btn[active="true"]  → stile del pulsante selezionato
                                         (usa le "proprietà dinamiche" di Qt)

Il foglio di stile viene applicato globalmente all'intera app
tramite app.setStyleSheet() nel main().
"""
APP_STYLE = """
* {
    font-family: "Segoe UI", "Ubuntu", "Helvetica Neue", Arial, sans-serif;
}

QMainWindow, QWidget#root {
    background-color: #F0F4F8;
}

/* ── SIDEBAR ──────────────────────────────────────────────────────── */

QFrame#sidebar {
    background-color: #1A2035;
    border: none;
}

QLabel#app_name {
    color: #F8FAFC;
    font-size: 16px;
    font-weight: 700;
}

QLabel#app_sub {
    color: #475569;
    font-size: 10px;
}

QPushButton#nav_btn {
    background-color: transparent;
    color: #94A3B8;
    border: none;
    border-radius: 8px;
    padding: 10px 12px 10px 14px;
    text-align: left;
    font-size: 12px;
}
QPushButton#nav_btn:hover {
    background-color: #243050;
    color: #E2E8F0;
}
QPushButton#nav_btn[active="true"] {
    background-color: #2563EB;
    color: #FFFFFF;
    font-weight: 700;
}

QLabel#stat_key { color: #475569; font-size: 10px; }
QLabel#stat_val { color: #CBD5E1; font-size: 11px; font-weight: 700; }

/* ── BARRA TITOLO PAGINA ──────────────────────────────────────────── */

QFrame#page_hdr {
    background-color: #FFFFFF;
    border-bottom: 1px solid #E2E8F0;
}
QLabel#page_title { color: #1E293B; font-size: 18px; font-weight: 700; }
QLabel#page_sub   { color: #64748B; font-size: 11px; }

/* ── CARD ─────────────────────────────────────────────────────────── */

QFrame#card {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
}
QFrame#rif_card {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
}

/* ── CAMPI INPUT ──────────────────────────────────────────────────── */

QLabel#field_lbl {
    color: #64748B;
    font-size: 10px;
    font-weight: 700;
}

QLineEdit {
    border: 1.5px solid #CBD5E1;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 12px;
    background-color: #FFFFFF;
    color: #1E293B;
    selection-background-color: #BFDBFE;
}
QLineEdit:focus {
    border-color: #2563EB;
    background-color: #F8FBFF;
}

/* ── PULSANTI ─────────────────────────────────────────────────────── */

QPushButton#add_btn {
    background-color: #2563EB;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 9px 22px;
    font-size: 13px;
    font-weight: 700;
    min-width: 160px;
}
QPushButton#add_btn:hover   { background-color: #1D4ED8; }
QPushButton#add_btn:pressed { background-color: #1E40AF; }

QPushButton#del_btn {
    background-color: transparent;
    color: #DC2626;
    border: 1px solid #FECACA;
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 11px;
}
QPushButton#del_btn:hover {
    background-color: #FEF2F2;
    border-color: #DC2626;
}

/* ── TABELLE ──────────────────────────────────────────────────────── */

QTableWidget {
    border: none;
    background-color: #FFFFFF;
    gridline-color: #F1F5F9;
    alternate-background-color: #F8FAFC;
    font-size: 12px;
    color: #1E293B;
    selection-background-color: #DBEAFE;
    outline: none;
}
QTableWidget::item {
    padding: 0px 8px;
    border-bottom: 1px solid #F1F5F9;
}
QTableWidget::item:selected {
    background-color: #DBEAFE;
    color: #1E293B;
}

QHeaderView { background-color: #F8FAFC; }
QHeaderView::section {
    background-color: #F8FAFC;
    color: #64748B;
    border: none;
    border-bottom: 2px solid #E2E8F0;
    padding: 7px 10px;
    font-size: 10px;
    font-weight: 700;
}

/* ── SCROLL ───────────────────────────────────────────────────────── */

QScrollArea { border: none; background-color: transparent; }

QScrollBar:vertical {
    background: transparent;
    width: 5px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #CBD5E1;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }

/* ── ETICHETTE VARIE ──────────────────────────────────────────────── */

QLabel#section_lbl  { color: #1E293B; font-size: 13px; font-weight: 700; }

QLabel#err_badge {
    background-color: #DBEAFE;
    color: #1D4ED8;
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 700;
}

QLabel#rif_total  { color: #059669; font-size: 12px; font-weight: 700; }
QLabel#big_total  { color: #2563EB; font-size: 40px; font-weight: 700; }
QLabel#total_unit { color: #64748B; font-size: 12px; }
QLabel#count_lbl  { color: #94A3B8; font-size: 11px; }
QLabel#sum_hdr    { color: #1E293B; font-size: 13px; font-weight: 700; }
QLabel#no_data    { color: #94A3B8; font-size: 13px; }

/* Pulsante aggiornamento nella sidebar */
QPushButton#update_btn {
    background-color: #059669;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 700;
    text-align: left;
}
QPushButton#update_btn:hover   { background-color: #047857; }
QPushButton#update_btn:pressed { background-color: #065F46; }
QPushButton#update_btn:disabled {
    background-color: #1A2035;
    color: #475569;
    border: 1px solid #243050;
}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# FUNZIONI DI SUPPORTO (helper)
# ═══════════════════════════════════════════════════════════════════════════════

def _field(label_text: str, placeholder: str = "") -> tuple:
    """
    Crea un blocco "etichetta + campo di testo" usato nel form.

    Struttura:
        QWidget (contenitore verticale)
          ├── QLabel  (es. "PRODUTTORE")
          └── QLineEdit (campo di input)

    Restituisce una tupla (contenitore, QLineEdit) così il chiamante
    può accedere al contenitore per aggiungerlo al layout, e al campo
    per leggerne il valore quando l'utente clicca "Aggiungi".

    Parametri:
        label_text  → testo dell'etichetta (viene reso maiuscolo nel CSS)
        placeholder → testo grigio di esempio mostrato quando il campo è vuoto
    """
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)  # nessun margine interno
    lay.setSpacing(5)                   # 5px tra etichetta e campo

    lbl = QLabel(label_text.upper())
    lbl.setObjectName("field_lbl")  # collegato allo stile QLabel#field_lbl

    entry = QLineEdit()
    entry.setPlaceholderText(placeholder)
    entry.setMinimumHeight(36)

    lay.addWidget(lbl)
    lay.addWidget(entry)
    return w, entry  # restituiamo entrambi


def _item(text: str, align=Qt.AlignmentFlag.AlignLeft) -> QTableWidgetItem:
    """
    Crea una cella di tabella con testo e allineamento verticale centrato.

    QTableWidgetItem è l'oggetto che Qt mette dentro ogni cella.
    AlignVCenter | AlignLeft = testo centrato verticalmente, allineato a sinistra.

    Questo helper evita di ripetere sempre le stesse tre righe
    ogni volta che si popola una riga della tabella.
    """
    it = QTableWidgetItem(str(text))
    it.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | align)
    return it


# ═══════════════════════════════════════════════════════════════════════════════
# AGGIORNAMENTI AUTOMATICI
# ═══════════════════════════════════════════════════════════════════════════════

class UpdateChecker(QThread):
    """Controlla in background se esiste una nuova release su GitHub."""
    update_available = pyqtSignal(str, str)  # (versione, download_url)

    def run(self):
        try:
            api = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(api, headers={"User-Agent": "WasteLog"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            remote = data.get("tag_name", "").lstrip("v")
            if not remote or remote == VERSION:
                return

            url = ""
            for asset in data.get("assets", []):
                if asset["name"].lower().endswith(".exe"):
                    url = asset["browser_download_url"]
                    break

            self.update_available.emit(remote, url)
        except Exception:
            pass


class FileDownloader(QThread):
    """Scarica un file in background e notifica quando ha finito."""
    done  = pyqtSignal(str)   # percorso file scaricato
    error = pyqtSignal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            tmp = tempfile.mktemp(suffix=".exe")
            urllib.request.urlretrieve(self.url, tmp)
            self.done.emit(tmp)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# PAGINA 1 — INSERIMENTO (FormPage)
# ═══════════════════════════════════════════════════════════════════════════════

class FormPage(QWidget):
    """
    Prima pagina dell'app: permette di inserire nuovi record e
    visualizza la lista completa di tutti quelli già presenti.

    SEGNALI
    -------
    record_added: emesso ogni volta che un record viene aggiunto o eliminato.
    MainWindow è in ascolto su questo segnale per aggiornare le altre pagine.

    LAYOUT
    ------
    QVBoxLayout (verticale)
      ├── Card form (QFrame#card)
      │     ├── Titolo "Nuovo Record"
      │     ├── QGridLayout 3×2 con i 6 campi
      │     └── Riga con il pulsante "Aggiungi"
      ├── Riga titolo tabella + contatore record
      └── Card tabella (QFrame#card)
            └── QTableWidget con tutti i record
    """

    # Segnale personalizzato: nessun dato allegato (solo notifica)
    record_added = pyqtSignal()

    def __init__(self, db: Database, parent=None):
        """
        Parametri:
            db     → istanza del database (passata dalla MainWindow)
            parent → widget genitore (Qt lo gestisce internamente)
        """
        super().__init__(parent)
        self.db = db  # salviamo il riferimento al database
        self._build()  # costruiamo l'interfaccia

    def _build(self):
        """Costruisce tutti i widget e i layout della pagina."""

        # Layout verticale principale con margini e spaziatura
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 16)
        root.setSpacing(14)

        # ── Card del form ──────────────────────────────────────────
        card = QFrame()
        card.setObjectName("card")
        cly = QVBoxLayout(card)
        cly.setContentsMargins(20, 14, 20, 16)
        cly.setSpacing(12)

        # Titolo interno alla card
        lbl = QLabel("Nuovo Record")
        lbl.setObjectName("section_lbl")
        cly.addWidget(lbl)

        # Griglia 3 righe × 2 colonne per i campi del form
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        # Riga 0: Produttore (colonna 0) | Codice ERR (colonna 1)
        w, self.f_prod  = _field("Produttore", "es. Mario Rossi Srl")
        grid.addWidget(w, 0, 0)
        w, self.f_err   = _field("Codice ERR", "es. 15 01 01")
        grid.addWidget(w, 0, 1)

        # Riga 1: Unità Locale | Destinatario
        w, self.f_ind   = _field("Unità Locale", "es. Via Roma 10, Milano")
        grid.addWidget(w, 1, 0)
        w, self.f_dest  = _field("Destinatario", "es. Smaltimenti Nord Srl")
        grid.addWidget(w, 1, 1)

        # Riga 2: Peso
        w, self.f_peso  = _field("Peso (kg)", "es. 250.5")
        grid.addWidget(w, 2, 0)

        cly.addLayout(grid)

        # Riga con pulsante allineato a destra
        btn_row = QHBoxLayout()
        btn_row.addStretch()  # spinge il pulsante verso destra

        self.add_btn = QPushButton("＋   Aggiungi Record")
        self.add_btn.setObjectName("add_btn")
        # Cambia il cursore del mouse in "manina" quando si passa sopra
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # Collega il click al metodo _add (slot)
        self.add_btn.clicked.connect(self._add)
        # Scorciatoia da tastiera: Invio per aggiungere
        self.add_btn.setShortcut("Return")
        btn_row.addWidget(self.add_btn)
        cly.addLayout(btn_row)

        root.addWidget(card)

        # ── Intestazione tabella record ────────────────────────────
        tbl_hdr = QHBoxLayout()
        lbl2 = QLabel("Tutti i Record")
        lbl2.setObjectName("section_lbl")
        tbl_hdr.addWidget(lbl2)
        tbl_hdr.addStretch()
        # Contatore aggiornato dinamicamente dopo ogni inserimento/elimina
        self.count_lbl = QLabel("0 record")
        self.count_lbl.setObjectName("count_lbl")
        tbl_hdr.addWidget(self.count_lbl)
        root.addLayout(tbl_hdr)

        # ── Card della tabella ─────────────────────────────────────
        tbl_card = QFrame()
        tbl_card.setObjectName("card")
        tly = QVBoxLayout(tbl_card)
        tly.setContentsMargins(0, 0, 0, 0)  # la tabella occupa tutta la card
        tly.setSpacing(0)

        # Colonne della tabella (l'ultima "" è per i pulsanti Elimina)
        cols = ["Produttore", "Unità Locale", "Codice ERR",
                "Destinatario", "Peso (kg)", ""]
        self.table = QTableWidget(0, len(cols))  # 0 righe iniziali, N colonne
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setAlternatingRowColors(True)  # righe alternate colorate
        # Selezione per riga intera (non cella singola)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # Impedisce la modifica diretta delle celle
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)          # nasconde la griglia
        self.table.verticalHeader().setVisible(False)  # nasconde numeri di riga
        self.table.setMinimumHeight(200)

        # Configurazione della larghezza delle colonne:
        hv = self.table.horizontalHeader()
        hv.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)           # Produttore
        hv.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)           # Unità Locale
        hv.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Codice ERR
        hv.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)           # Destinatario
        hv.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Peso
        # Colonna pulsante: larghezza fissa
        hv.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        hv.resizeSection(5, 74)

        tly.addWidget(self.table)
        root.addWidget(tbl_card)

        # Carica i dati esistenti nel database (se presenti)
        self.refresh()

    # ── Slot: aggiunta record ──────────────────────────────────────

    def _add(self):
        """
        Chiamato quando l'utente clicca "Aggiungi Record" o preme Invio.

        Flusso:
        1. Legge i valori dai campi di testo.
        2. Controlla che nessun campo sia vuoto.
        3. Valida il peso (deve essere un numero positivo).
        4. Chiama db.insert() per salvare nel database.
        5. Svuota i campi e sposta il cursore sul primo campo.
        6. Aggiorna la tabella e notifica le altre pagine.
        """
        # Costruiamo un dizionario campo→valore per facilitare la validazione
        vals = {
            "Produttore":   self.f_prod.text().strip(),
            "Unità Locale": self.f_ind.text().strip(),
            "Codice ERR":   self.f_err.text().strip(),
            "Destinatario": self.f_dest.text().strip(),
            "Peso":         self.f_peso.text().strip(),
        }

        # Trova i campi lasciati vuoti
        missing = [k for k, v in vals.items() if not v]
        if missing:
            QMessageBox.warning(
                self, "Campi mancanti",
                f"Compila i seguenti campi: {', '.join(missing)}"
            )
            return  # fermiamo l'esecuzione senza aggiungere nulla

        # Valida il peso: deve essere un numero decimale positivo
        try:
            # Accettiamo sia il punto (1250.5) che la virgola (1250,5)
            peso = float(vals["Peso"].replace(",", "."))
            if peso <= 0:
                raise ValueError("il peso deve essere positivo")
        except ValueError:
            QMessageBox.warning(
                self, "Peso non valido",
                "Inserisci un numero positivo per il Peso (es. 250 o 1250.5)."
            )
            return

        # Tutto ok: salva nel database
        self.db.insert(
            vals["Produttore"], "", vals["Unità Locale"],
            vals["Codice ERR"], vals["Destinatario"], peso
        )

        # Svuota tutti i campi del form per il prossimo inserimento
        for f in (self.f_prod, self.f_ind,
                  self.f_err, self.f_dest, self.f_peso):
            f.clear()
        self.f_prod.setFocus()  # riporta il cursore al primo campo

        # Aggiorna la tabella e informa le altre pagine
        self.refresh()
        self.record_added.emit()  # emette il segnale

    # ── Slot: eliminazione record ──────────────────────────────────

    def _delete(self, rid: int):
        """
        Chiamato quando l'utente clicca "Elimina" su una riga.

        rid → ID univoco del record nel database (intero).
        Mostra una finestra di conferma prima di procedere.
        """
        risposta = QMessageBox.question(
            self, "Elimina record",
            "Sei sicuro di voler eliminare questo record?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if risposta == QMessageBox.StandardButton.Yes:
            self.db.delete(rid)   # rimuove dal database
            self.refresh()        # aggiorna la tabella visiva
            self.record_added.emit()  # notifica le altre pagine

    # ── Aggiornamento tabella ──────────────────────────────────────

    def refresh(self):
        """
        Ricostruisce la tabella leggendo tutti i record dal database.

        Viene chiamata:
        - al primo avvio (in _build)
        - dopo ogni inserimento
        - dopo ogni eliminazione
        - quando l'utente torna su questa pagina

        Nota: setRowCount(0) svuota la tabella prima di ripopolarla.
        Questo è più semplice che aggiornare solo le righe cambiate,
        e con poche centinaia di record è abbastanza veloce.
        """
        records = self.db.all()
        self.table.setRowCount(0)  # svuota la tabella

        for r in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 40)

            # Riempie le prime 4 colonne con i dati testuali
            for col, key in enumerate(
                ["produttore", "indirizzo", "codice_err", "destinatario"]
            ):
                self.table.setItem(row, col, _item(r[key]))

            # Colonna peso: allineato a destra, formato con 2 decimali
            self.table.setItem(
                row, 4,
                _item(f"{r['peso']:,.2f}", Qt.AlignmentFlag.AlignRight)
            )

            # Colonna azioni: inserisce un pulsante QPushButton nella cella
            btn = QPushButton("Elimina")
            btn.setObjectName("del_btn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            # IMPORTANTE: la lambda cattura rid=r["id"] per evitare il
            # problema di "late binding" nelle lambda nei loop Python.
            rid = r["id"]
            btn.clicked.connect(lambda _, x=rid: self._delete(x))
            self.table.setCellWidget(row, 5, btn)  # inserisce widget nella cella

        # Aggiorna il contatore in alto a destra ("12 record inseriti")
        n = len(records)
        self.count_lbl.setText(f"{n} record{'i' if n != 1 else ''}")


# ═══════════════════════════════════════════════════════════════════════════════
# COMPONENTE — SCHEDA RIF SINGOLA (RifCard)
# ═══════════════════════════════════════════════════════════════════════════════

class RifCard(QFrame):
    """
    Card visiva che rappresenta una singola Scheda RIF.

    Una Scheda RIF raggruppa tutte le "bustine" (record) che condividono
    lo stesso Codice ERR. Per ogni codice ERR viene creata una RifCard.

    LAYOUT INTERNO
    --------------
    QVBoxLayout
      ├── Riga header (QHBoxLayout)
      │     ├── Badge "ERR 15 01 01" (QLabel#err_badge)
      │     ├── "N bustine" (QLabel#count_lbl)
      │     └── "Totale: X kg" (QLabel#rif_total)
      └── Tabella bustine (QTableWidget)
            colonne: Produttore | Città | Indirizzo | Destinatario | Peso
    """

    def __init__(self, codice_err: str, records: list, parent=None):
        """
        Parametri:
            codice_err → es. "15 01 01"
            records    → lista di dizionari (una bustina per elemento)
        """
        super().__init__(parent)
        self.setObjectName("rif_card")  # aggancia lo stile QFrame#rif_card
        self._build(codice_err, records)

    def _build(self, codice_err: str, records: list):
        """Costruisce l'header e la tabella della scheda."""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(10)

        # ── Header della scheda ────────────────────────────────────
        hdr = QHBoxLayout()

        # Badge blu con il codice ERR
        badge = QLabel(f"  ERR  {codice_err}  ")
        badge.setObjectName("err_badge")

        # Contatore bustine ("3 bustine")
        n = len(records)
        n_lbl = QLabel("")
        n_lbl.setObjectName("count_lbl")

        # Totale peso per questa scheda (somma di tutte le bustine)
        total = sum(r["peso"] for r in records)
        t_lbl = QLabel(f"Totale:  {total:,.2f} kg")
        t_lbl.setObjectName("rif_total")

        hdr.addWidget(badge)
        hdr.addSpacing(6)
        hdr.addWidget(n_lbl)
        hdr.addStretch()  # spinge il totale verso destra
        hdr.addWidget(t_lbl)
        lay.addLayout(hdr)

        # ── Tabella delle bustine ──────────────────────────────────
        cols = ["Produttore", "Unità Locale", "Destinatario", "Peso (kg)"]
        tbl = QTableWidget(len(records), len(cols))
        tbl.setHorizontalHeaderLabels(cols)
        tbl.setAlternatingRowColors(True)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tbl.setShowGrid(False)
        tbl.verticalHeader().setVisible(False)

        # Configurazione larghezze colonne
        hv = tbl.horizontalHeader()
        hv.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)           # Produttore
        hv.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)           # Unità Locale
        hv.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)           # Destinatario
        hv.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Peso

        # Popola le righe con i dati delle bustine
        for row, r in enumerate(records):
            tbl.setRowHeight(row, 38)
            for col, key in enumerate(
                ["produttore", "indirizzo", "destinatario"]
            ):
                tbl.setItem(row, col, _item(r[key]))
            tbl.setItem(row, 3,
                        _item(f"{r['peso']:,.2f}", Qt.AlignmentFlag.AlignRight))

        tbl.setFixedHeight(32 + 38 * len(records) + 2)
        lay.addWidget(tbl)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGINA 2 — SCHEDE RIF (RifPage)
# ═══════════════════════════════════════════════════════════════════════════════

class RifPage(QScrollArea):
    """
    Seconda pagina: mostra tutte le Schede RIF in una lista scorrevole.

    Estende QScrollArea invece di QWidget perché le schede RIF possono
    essere molte e non stare tutte nello schermo: la scrollbar verticale
    permette di scorrere verso il basso.

    STRUTTURA
    ---------
    QScrollArea
      └── _container (QWidget, scorrevole)
            └── _lay (QVBoxLayout)
                  ├── RifCard("15 01 01", [...])
                  ├── RifCard("20 03 01", [...])
                  ├── ...
                  └── stretch (occupa lo spazio rimanente in basso)
    """

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        # setWidgetResizable(True): il contenitore interno si ridimensiona
        # automaticamente quando la finestra cambia dimensione
        self.setWidgetResizable(True)
        # Nasconde la scrollbar orizzontale (non serve)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Contenitore interno (il widget "scorrevole")
        self._container = QWidget()
        self._lay = QVBoxLayout(self._container)
        self._lay.setContentsMargins(20, 16, 20, 16)
        self._lay.setSpacing(12)

        self.setWidget(self._container)

    def refresh(self):
        """
        Svuota e ricostruisce l'elenco delle schede RIF.

        Viene chiamata ogni volta che l'utente naviga su questa pagina
        o quando vengono aggiunti/rimossi record.

        Tecnica: svuota il layout rimuovendo tutti i widget figli,
        poi li ricrea da zero leggendo i dati aggiornati dal database.
        deleteLater() è il modo Qt di distruggere un widget in sicurezza
        (lo elimina dopo che Qt ha finito di processare gli eventi correnti).
        """
        # Rimuove tutti i widget esistenti dal layout
        while self._lay.count():
            item = self._lay.takeAt(0)  # rimuove il primo elemento
            if item.widget():
                item.widget().deleteLater()  # distrugge il widget

        by_err = self.db.by_err()  # dizionario {codice_err: [record...]}

        if not by_err:
            # Messaggio "nessun dato" se il database è vuoto
            lbl = QLabel("Nessun dato.\nVai su Inserimento per aggiungere record.")
            lbl.setObjectName("no_data")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._lay.addWidget(lbl)
        else:
            # Crea una RifCard per ogni codice ERR (in ordine alfabetico)
            for err_code in sorted(by_err.keys()):
                self._lay.addWidget(RifCard(err_code, by_err[err_code]))

        # Stretch in fondo: spinge le card verso l'alto se sono poche
        self._lay.addStretch()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGINA 3 — RIEPILOGO (SummaryPage)
# ═══════════════════════════════════════════════════════════════════════════════

class SummaryPage(QWidget):
    """
    Terza pagina: mostra le aggregazioni (somme) dei dati.

    LAYOUT
    ------
    QVBoxLayout (verticale)
      ├── Card peso totale (grande numero blu al centro)
      └── QHBoxLayout (orizzontale, due colonne)
            ├── Card "Per Produttore" (QTableWidget)
            └── Card "Per Unità Locale" (QTableWidget)
    """

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._build()

    def _build(self):
        """Costruisce la struttura fissa della pagina."""
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 16)
        root.setSpacing(14)

        # ── Card peso totale ───────────────────────────────────────
        tc = QFrame()
        tc.setObjectName("card")
        tly = QVBoxLayout(tc)
        tly.setContentsMargins(28, 16, 28, 16)
        tly.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tly.setSpacing(2)

        # Il numero grande (es. "12.450,00") — aggiornato in refresh()
        self.total_lbl = QLabel("0,00")
        self.total_lbl.setObjectName("big_total")
        self.total_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Unità di misura sotto il numero
        unit_lbl = QLabel("kg — peso totale")
        unit_lbl.setObjectName("total_unit")
        unit_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Contatore record (es. "12 record inseriti")
        self.n_lbl = QLabel("")
        self.n_lbl.setObjectName("count_lbl")
        self.n_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tly.addWidget(self.total_lbl)
        tly.addWidget(unit_lbl)
        tly.addSpacing(4)
        tly.addWidget(self.n_lbl)
        root.addWidget(tc)

        cols_row = QHBoxLayout()
        cols_row.setSpacing(14)

        # Crea le due card con le rispettive tabelle.
        # _make_card aggiunge la card direttamente a cols_row e restituisce
        # il QTableWidget interno (che aggiorniamo in refresh).
        self.prod_unita_tbl = self._make_card(
            cols_row, "Per Produttore e Unità Locale",
            ["RT", "Produttore", "Unità Locale", "Peso Totale (kg)"]
        )
        self.err_tbl = self._make_card(
            cols_row, "Per Codice ERR",
            ["Codice ERR", "Peso Totale (kg)"]
        )
        self.dest_tbl = self._make_card(
            cols_row, "Per Destinazione",
            ["Destinatario", "Peso Totale (kg)"]
        )
        root.addLayout(cols_row)

    def _make_card(self, parent_layout: QHBoxLayout, title: str,
                   headers: list) -> QTableWidget:
        """
        Crea una card con intestazione e tabella di aggregazione.

        Aggiunge la card a parent_layout e restituisce il QTableWidget
        interno per poterlo riempire in refresh().

        Parametri:
            parent_layout → il layout a cui aggiungere questa card
            title         → titolo in cima alla card (es. "Per Produttore")
            headers       → nomi delle colonne della tabella
        """
        card = QFrame()
        card.setObjectName("card")
        cly = QVBoxLayout(card)
        cly.setContentsMargins(0, 0, 0, 0)
        cly.setSpacing(0)

        # Intestazione con il titolo della sezione
        hdr_w = QWidget()
        hly = QHBoxLayout(hdr_w)
        hly.setContentsMargins(16, 10, 16, 8)
        lbl = QLabel(title)
        lbl.setObjectName("sum_hdr")
        hly.addWidget(lbl)
        cly.addWidget(hdr_w)

        # Tabella con N colonne: tutte elastiche tranne l'ultima (peso)
        ncols = len(headers)
        tbl = QTableWidget(0, ncols)
        tbl.setHorizontalHeaderLabels(headers)
        tbl.setAlternatingRowColors(True)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tbl.setShowGrid(False)
        tbl.verticalHeader().setVisible(False)
        tbl.setMinimumHeight(160)

        hv = tbl.horizontalHeader()
        for i in range(ncols - 1):
            hv.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        hv.setSectionResizeMode(ncols - 1, QHeaderView.ResizeMode.ResizeToContents)

        cly.addWidget(tbl)
        parent_layout.addWidget(card)  # aggiunge la card al layout genitore
        return tbl

    def _fill(self, tbl: QTableWidget, rows):
        """
        Riempie una tabella di aggregazione con le righe di dati.

        rows → lista di tuple dove l'ultimo elemento è sempre il peso (float)
        e i precedenti sono stringhe testuali.
        """
        tbl.setRowCount(0)
        for row_data in rows:
            row = tbl.rowCount()
            tbl.insertRow(row)
            tbl.setRowHeight(row, 38)
            for col, val in enumerate(row_data[:-1]):
                tbl.setItem(row, col, _item(str(val)))
            tbl.setItem(row, len(row_data) - 1,
                        _item(f"{row_data[-1]:,.2f}", Qt.AlignmentFlag.AlignRight))

    def refresh(self):
        """
        Aggiorna tutti i valori della pagina leggendo il database.

        Viene chiamata ogni volta che l'utente naviga su questa pagina
        o quando vengono aggiunti/rimossi record (tramite il segnale
        record_added di FormPage).
        """
        # Aggiorna il numero grande in cima
        self.total_lbl.setText(f"{self.db.total():,.2f}")

        # Aggiorna il contatore record
        n = self.db.count()
        self.n_lbl.setText(f"{n} record{'i' if n != 1 else ''} inseriti")

        # Aggiorna la tabella "Per Produttore e Unità Locale"
        self._fill(
            self.prod_unita_tbl,
            [(f"RT{i}", r["produttore"], r["ul"], r["totale"])
             for i, r in enumerate(self.db.sum_produttore_unita(), start=1)]
        )

        # Aggiorna la tabella "Per Codice ERR"
        self._fill(
            self.err_tbl,
            [(r["codice_err"], r["totale"]) for r in self.db.sum_codice_err()]
        )

        # Aggiorna la tabella "Per Destinazione"
        self._fill(
            self.dest_tbl,
            [(r["destinatario"], r["totale"]) for r in self.db.sum_destinatario()]
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR (navigazione laterale)
# ═══════════════════════════════════════════════════════════════════════════════

class Sidebar(QFrame):
    """
    Pannello di navigazione a sinistra con sfondo scuro.

    Contiene:
    - Il nome dell'app in cima
    - Tre pulsanti di navigazione (uno per pagina)
    - Informazioni sul file database in fondo

    SEGNALI
    -------
    nav_changed(int): emesso quando l'utente clicca un pulsante di navigazione.
    Porta l'indice della pagina selezionata (0, 1 o 2).
    MainWindow riceve questo segnale e cambia la pagina visibile nello stack.
    """

    nav_changed    = pyqtSignal(int)         # indice pagina selezionata
    update_clicked = pyqtSignal(str, str)   # (versione, download_url)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(210)
        self._btns: list[QPushButton] = []
        self._update_version = ""
        self._update_url     = ""
        self._build()

    def _build(self):
        """Costruisce il contenuto della sidebar."""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 20, 10, 16)
        lay.setSpacing(3)

        # ── Logo / nome app ────────────────────────────────────────
        logo = QWidget()
        lly = QVBoxLayout(logo)
        lly.setContentsMargins(8, 0, 8, 0)
        lly.setSpacing(2)

        name_lbl = QLabel("WasteLog")
        name_lbl.setObjectName("app_name")

        sub_lbl = QLabel("Formulari Rifiuti")
        sub_lbl.setObjectName("app_sub")

        lly.addWidget(name_lbl)
        lly.addWidget(sub_lbl)
        lay.addWidget(logo)
        lay.addSpacing(14)

        # ── Pulsanti di navigazione ────────────────────────────────
        # Ogni tupla: (emoji icona, testo etichetta)
        # L'indice i corrisponde alla pagina nello QStackedWidget
        for i, (icon, label) in enumerate([
            ("📝", "Inserimento"),    # indice 0 → FormPage
            ("📋", "Schede RIF"),     # indice 1 → RifPage
            ("📊", "Riepilogo"),      # indice 2 → SummaryPage
        ]):
            btn = QPushButton(f"  {icon}   {label}")
            btn.setObjectName("nav_btn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            # Proprietà dinamica "active": usata nel QSS per cambiare stile
            btn.setProperty("active", "false")
            btn.setMinimumHeight(40)
            # Lambda con default i=i per catturare il valore corrente
            # (evita il problema di late binding nei loop)
            btn.clicked.connect(lambda _, x=i: self._select(x))
            self._btns.append(btn)
            lay.addWidget(btn)

        lay.addStretch()  # spinge il separatore e le info verso il basso

        # ── Separatore ─────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)  # linea orizzontale
        sep.setStyleSheet("color: #243050; background-color: #243050;")
        sep.setFixedHeight(1)
        lay.addWidget(sep)
        lay.addSpacing(8)

        # ── Bottone aggiornamento (nascosto finché non c'è update) ──
        self.update_btn = QPushButton("  ↓   Aggiornamento disponibile")
        self.update_btn.setObjectName("update_btn")
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.setVisible(False)
        self.update_btn.clicked.connect(
            lambda: self.update_clicked.emit(self._update_version, self._update_url)
        )
        lay.addWidget(self.update_btn)
        lay.addSpacing(8)

        # ── Info database ──────────────────────────────────────────
        info = QWidget()
        ily = QVBoxLayout(info)
        ily.setContentsMargins(8, 0, 8, 0)
        ily.setSpacing(4)
        k = QLabel("Archivio locale")
        k.setObjectName("stat_key")
        v = QLabel("wastelog.db")
        v.setObjectName("stat_val")
        ily.addWidget(k)
        ily.addWidget(v)
        lay.addWidget(info)

        # Seleziona il primo pulsante all'avvio
        self._select(0)

    def _select(self, idx: int):
        """
        Aggiorna l'aspetto visivo dei pulsanti e notifica la MainWindow.

        Quando l'utente clicca un pulsante:
        1. Tutti i pulsanti vengono marcati come non attivi (active="false")
        2. Il pulsante cliccato viene marcato come attivo (active="true")
        3. Qt ricalcola lo stile (unpolish/polish) per applicare il QSS
        4. Viene emesso il segnale nav_changed con l'indice della pagina

        Perché unpolish/polish?
        Le proprietà dinamiche Qt (setProperty) non aggiornano
        automaticamente lo stile. Bisogna "scollegare" (unpolish) e
        "ricollegare" (polish) lo stile per forzare il ricalcolo.
        """
        for i, btn in enumerate(self._btns):
            active = "true" if i == idx else "false"
            btn.setProperty("active", active)
            btn.style().unpolish(btn)  # rimuove lo stile corrente
            btn.style().polish(btn)    # riapplica lo stile aggiornato

        self.nav_changed.emit(idx)

    def show_update(self, version: str, url: str):
        """Mostra il bottone di aggiornamento con la versione disponibile."""
        self._update_version = version
        self._update_url     = url
        self.update_btn.setText(f"  ↓   v{version} disponibile")
        self.update_btn.setVisible(True)


# ═══════════════════════════════════════════════════════════════════════════════
# FINESTRA PRINCIPALE (MainWindow)
# ═══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    """
    Coordina tutti i componenti dell'applicazione.

    Responsabilità:
    - Crea l'istanza del database (passata a tutti i widget che ne hanno bisogno)
    - Costruisce il layout principale (sidebar + area destra)
    - Gestisce il cambio di pagina tramite QStackedWidget
    - Ascolta il segnale record_added di FormPage per aggiornare
      le altre pagine quando i dati cambiano

    NON contiene logica di business: si limita a collegare i componenti.
    """

    # Testo del titolo e sottotitolo per ciascuna delle 3 pagine
    _HEADERS = [
        ("Inserimento",  "Aggiungi nuovi record al formulario"),
        ("Schede RIF",   "Record raggruppati per Codice ERR"),
        ("Riepilogo",    "Totali aggregati per produttore e unità locale"),
    ]

    def __init__(self):
        super().__init__()
        self.db = Database()  # unica istanza del database per tutta l'app
        self.setWindowTitle("WasteLog — Gestione Formulari Rifiuti")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)
        self._build()

    def _build(self):
        """Assembla tutti i widget nella finestra principale."""

        # QMainWindow richiede un "central widget" come contenitore principale
        root = QWidget()
        root.setObjectName("root")  # per il QSS: QWidget#root → sfondo chiaro
        self.setCentralWidget(root)

        # Layout orizzontale principale: sidebar a sinistra, contenuto a destra
        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)  # nessun margine (sidebar a bordo)
        main.setSpacing(0)

        # ── Sidebar ────────────────────────────────────────────────
        self.sidebar = Sidebar()
        self.sidebar.nav_changed.connect(self._switch)
        self.sidebar.update_clicked.connect(self._on_update_clicked)
        main.addWidget(self.sidebar)

        # ── Area destra (header + pagine) ─────────────────────────
        right = QWidget()
        right.setObjectName("root")  # stesso sfondo chiaro
        rly = QVBoxLayout(right)
        rly.setContentsMargins(0, 0, 0, 0)
        rly.setSpacing(0)

        # Barra del titolo in cima all'area destra
        self.hdr_frame = QFrame()
        self.hdr_frame.setObjectName("page_hdr")
        self.hdr_frame.setFixedHeight(58)
        hly = QHBoxLayout(self.hdr_frame)
        hly.setContentsMargins(24, 0, 24, 0)

        # Titolo e sottotitolo della pagina corrente
        self.pg_title = QLabel("Inserimento")
        self.pg_title.setObjectName("page_title")
        self.pg_sub = QLabel("Aggiungi nuovi record al formulario")
        self.pg_sub.setObjectName("page_sub")

        # Dispone titolo e sottotitolo in verticale dentro la barra
        vl = QVBoxLayout()
        vl.setSpacing(2)
        vl.addWidget(self.pg_title)
        vl.addWidget(self.pg_sub)
        hly.addLayout(vl)
        hly.addStretch()
        rly.addWidget(self.hdr_frame)

        # ── QStackedWidget: contiene le 3 pagine ──────────────────
        # QStackedWidget mostra un solo figlio alla volta.
        # _switch() chiama setCurrentIndex() per cambiare pagina.
        self.stack = QStackedWidget()

        # Creazione delle 3 pagine
        self.form_page    = FormPage(self.db)
        self.rif_page     = RifPage(self.db)
        self.summary_page = SummaryPage(self.db)

        # Quando FormPage segnala un cambiamento dati, aggiorniamo
        # le altre pagine se sono visibili
        self.form_page.record_added.connect(self._on_data_changed)

        # Le pagine vanno aggiunte nell'ordine: 0, 1, 2
        self.stack.addWidget(self.form_page)     # indice 0
        self.stack.addWidget(self.rif_page)      # indice 1
        self.stack.addWidget(self.summary_page)  # indice 2

        rly.addWidget(self.stack)
        main.addWidget(right)

        # ── Controllo aggiornamenti in background ──────────────────
        self._checker = UpdateChecker()
        self._checker.update_available.connect(self.sidebar.show_update)
        self._checker.start()

    # ── Slot: cambio pagina ────────────────────────────────────────

    def _switch(self, idx: int):
        """
        Cambia la pagina visibile quando l'utente clicca un pulsante
        nella sidebar.

        Oltre a cambiare pagina, aggiorna il testo del titolo/sottotitolo
        nella barra in alto e richiama refresh() sulle pagine che
        mostrano dati aggregati (RifPage e SummaryPage), in modo che
        abbiano sempre i dati più recenti.

        Parametri:
            idx → indice della pagina (0=Form, 1=RIF, 2=Riepilogo)
        """
        # Aggiorna il titolo nella barra superiore
        title, sub = self._HEADERS[idx]
        self.pg_title.setText(title)
        self.pg_sub.setText(sub)

        # Mostra la pagina selezionata
        self.stack.setCurrentIndex(idx)

        # Aggiorna i dati delle pagine "vista" quando vengono aperte
        if idx == 1:
            self.rif_page.refresh()
        elif idx == 2:
            self.summary_page.refresh()

    # ── Slot: aggiornamento dati ───────────────────────────────────

    def _on_data_changed(self):
        """
        Chiamato quando FormPage emette record_added (inserimento o eliminazione).
        """
        idx = self.stack.currentIndex()
        if idx == 1:
            self.rif_page.refresh()
        elif idx == 2:
            self.summary_page.refresh()

    # ── Slot: aggiornamento software ───────────────────────────────

    def _on_update_clicked(self, version: str, url: str):
        """Chiede conferma e avvia il download del nuovo eseguibile."""
        risposta = QMessageBox.question(
            self, "Aggiornamento disponibile",
            f"È disponibile la versione {version} di WasteLog.\n\n"
            "Vuoi scaricarla e installare l'aggiornamento adesso?\n"
            "L'applicazione verrà riavviata automaticamente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if risposta != QMessageBox.StandardButton.Yes:
            return

        if not getattr(sys, "frozen", False) or not url:
            webbrowser.open(
                f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
            )
            return

        self.sidebar.update_btn.setText("  ↓   Download in corso…")
        self.sidebar.update_btn.setEnabled(False)

        self._downloader = FileDownloader(url)
        self._downloader.done.connect(self._apply_update)
        self._downloader.error.connect(self._on_download_error)
        self._downloader.start()

    def _apply_update(self, new_exe: str):
        """Salva il nuovo EXE nella stessa cartella di quello corrente e apre Esplora File."""
        dest_dir = os.path.dirname(sys.executable)
        version = self.sidebar._update_version
        dest = os.path.join(dest_dir, f"WasteLog_{version}.exe")
        try:
            import shutil
            shutil.copy2(new_exe, dest)
            os.remove(new_exe)
        except Exception as e:
            self._on_download_error(f"Impossibile salvare il file:\n{e}")
            return

        subprocess.Popen(["explorer", f"/select,{dest}"])
        self.sidebar.update_btn.setText("  ↓   Aggiornamento disponibile")
        self.sidebar.update_btn.setEnabled(True)
        QMessageBox.information(
            self, "Aggiornamento scaricato",
            f"Il nuovo eseguibile è stato salvato in:\n{dest}\n\n"
            "Chiudi WasteLog e avvia il nuovo file per completare l'aggiornamento.",
        )

    def _on_download_error(self, msg: str):
        self.sidebar.update_btn.setText("  ↓   Aggiornamento disponibile")
        self.sidebar.update_btn.setEnabled(True)
        QMessageBox.critical(
            self, "Errore download",
            f"Impossibile scaricare l'aggiornamento:\n{msg}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# AVVIO DELL'APPLICAZIONE
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """
    Punto di ingresso dell'applicazione.

    Flusso:
    1. QApplication inizializza Qt e il ciclo degli eventi.
       sys.argv passa eventuali argomenti da riga di comando a Qt.
    2. setStyle("Fusion") applica uno stile cross-platform moderno
       (stesso aspetto su Windows, Linux e macOS).
    3. setStyleSheet(APP_STYLE) applica il foglio di stile globale.
    4. MainWindow() crea la finestra e tutti i widget figli.
    5. win.show() rende la finestra visibile.
    6. app.exec() avvia il ciclo degli eventi Qt (blocca fino alla chiusura).
    7. sys.exit() chiude il processo con il codice di uscita di Qt.
    """
    app = QApplication(sys.argv)
    app.setStyle("Fusion")          # stile base cross-platform
    app.setStyleSheet(APP_STYLE)    # sovrascrive lo stile con il nostro QSS

    win = MainWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    # Questo blocco viene eseguito solo quando il file è lanciato direttamente
    # (non quando viene importato come modulo da un altro file).
    main()
