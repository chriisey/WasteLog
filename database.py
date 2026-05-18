"""
database.py
-----------
Livello dati dell'applicazione.

Tutta la logica di accesso al database SQLite è centralizzata qui.
Il resto del programma non tocca mai SQL direttamente: usa solo i metodi
di questa classe. In questo modo, se in futuro si vuole cambiare database
(es. PostgreSQL), basta modificare solo questo file.

SQLite è un database "embedded": non richiede un server separato.
I dati vengono salvati in un singolo file (wastelog.db) sul disco locale.
"""

import sqlite3  # modulo standard Python per SQLite
import sys       # usato per rilevare se l'app è "congelata" da PyInstaller
from pathlib import Path  # gestione portabile dei percorsi di file


class Database:
    """
    Gestisce la connessione al database e tutte le operazioni CRUD
    (Create, Read, Update, Delete) sui record dei formulari rifiuti.

    Viene creata una sola istanza nella MainWindow e passata a tutte
    le pagine dell'interfaccia che ne hanno bisogno.
    """

    def __init__(self):
        """
        Inizializza la connessione al database SQLite.

        Strategia per il percorso del file:
        - Se l'app è "congelata" (distribuita come .exe con PyInstaller),
          sys.frozen è True e il file .db viene messo nella home dell'utente,
          così l'eseguibile rimane separato dai dati.
        - Durante lo sviluppo, il file viene creato nella stessa cartella
          del codice sorgente.
        """
        # Determina la cartella dove salvare il database
        if getattr(sys, "frozen", False):
            # Modalità eseguibile: usa la cartella home dell'utente
            # (es. C:\Users\Mario\ su Windows, /home/mario/ su Linux)
            base = Path.home()
        else:
            # Modalità sviluppo: usa la cartella del progetto
            base = Path(__file__).parent

        # Apre (o crea) il file wastelog.db nella cartella scelta
        self._conn = sqlite3.connect(str(base / "wastelog.db"))

        # row_factory = sqlite3.Row permette di accedere alle colonne
        # per nome (es. r["produttore"]) invece che per indice (es. r[0])
        self._conn.row_factory = sqlite3.Row

        # Crea le tabelle se non esistono ancora
        self._init()

    # ── Schema ────────────────────────────────────────────────────────────────

    def _init(self):
        """
        Crea la struttura del database al primo avvio.

        executescript() esegue più istruzioni SQL in blocco.
        CREATE TABLE IF NOT EXISTS è idempotente: non dà errore
        se la tabella esiste già, quindi è sicuro chiamarlo ogni volta.

        Struttura della tabella 'records':
          id           → chiave primaria, auto-incrementale
          produttore   → nome del produttore di rifiuti
          citta        → città dell'unità locale
          indirizzo    → indirizzo dell'unità locale
          codice_err   → codice europeo rifiuti (es. "15 01 01")
          destinatario → impianto di destinazione
          peso         → peso in kg (numero decimale)
          inserito_il  → data/ora di inserimento, calcolata automaticamente
        """
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS records (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                produttore   TEXT    NOT NULL,
                citta        TEXT    NOT NULL,
                indirizzo    TEXT    NOT NULL,
                codice_err   TEXT    NOT NULL,
                destinatario TEXT    NOT NULL,
                peso         REAL    NOT NULL,
                inserito_il  TEXT    DEFAULT (strftime('%d/%m/%Y %H:%M', 'now', 'localtime'))
            );
        """)
        # Salva le modifiche strutturali sul disco
        self._conn.commit()

    # ── Scrittura ─────────────────────────────────────────────────────────────

    def insert(self, produttore, citta, indirizzo, codice_err, destinatario, peso):
        """
        Inserisce un nuovo record (bustina) nel database.

        I parametri stringa vengono ripuliti con .strip() per rimuovere
        spazi accidentali all'inizio e alla fine.
        Il codice ERR viene convertito in maiuscolo per uniformità.
        Il peso viene sempre convertito in float per sicurezza.

        Il ? nella query è un "placeholder": SQLite sostituisce i valori
        in modo sicuro, prevenendo SQL injection.
        """
        self._conn.execute(
            "INSERT INTO records (produttore, citta, indirizzo, codice_err, destinatario, peso)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                produttore.strip(),
                citta.strip(),
                indirizzo.strip(),
                codice_err.strip().upper(),  # es. "15 01 01" → "15 01 01"
                destinatario.strip(),
                float(peso),
            ),
        )
        # commit() rende permanente l'inserimento su disco
        self._conn.commit()

    def delete(self, rid: int):
        """
        Elimina un record dato il suo ID univoco.

        L'ID viene passato dall'interfaccia quando l'utente clicca
        il pulsante "Elimina" su una riga della tabella.
        """
        self._conn.execute("DELETE FROM records WHERE id = ?", (rid,))
        self._conn.commit()

    # ── Lettura ───────────────────────────────────────────────────────────────

    def all(self):
        """
        Restituisce tutti i record ordinati per codice ERR e produttore.

        dict(r) converte ogni sqlite3.Row in un dizionario Python standard,
        più comodo da usare nell'interfaccia (es. r["produttore"]).

        L'ordinamento garantisce che la tabella mostri sempre i dati
        in modo coerente e leggibile.
        """
        return [
            dict(r)
            for r in self._conn.execute(
                "SELECT * FROM records ORDER BY codice_err, produttore"
            ).fetchall()
        ]

    def by_err(self):
        """
        Raggruppa i record per codice ERR in un dizionario Python.

        Struttura restituita:
          {
            "15 01 01": [record1, record2, ...],
            "20 03 01": [record3, ...],
            ...
          }

        Usato dalla pagina "Schede RIF" per costruire una card
        separata per ogni codice ERR.
        """
        grouped: dict = {}
        for r in self.all():
            # setdefault crea la lista se la chiave non esiste ancora
            grouped.setdefault(r["codice_err"], []).append(r)
        return grouped

    # ── Aggregazioni ──────────────────────────────────────────────────────────

    def sum_produttore(self):
        """
        Restituisce la somma dei pesi raggruppata per produttore.

        SQL GROUP BY aggrega tutte le righe con lo stesso produttore
        e SUM(peso) le somma. ORDER BY totale DESC mostra prima
        i produttori con più peso.

        Usata nella pagina "Riepilogo" per la tabella sinistra.
        """
        return self._conn.execute(
            "SELECT produttore, SUM(peso) totale"
            " FROM records"
            " GROUP BY produttore"
            " ORDER BY totale DESC"
        ).fetchall()

    def sum_unita(self):
        """
        Restituisce la somma dei pesi raggruppata per unità locale (indirizzo).

        Il campo indirizzo contiene l'unità locale completa (via e città).
        Usata nella pagina "Riepilogo" per la tabella centrale.
        """
        return self._conn.execute(
            "SELECT indirizzo AS ul, SUM(peso) totale"
            " FROM records"
            " GROUP BY indirizzo"
            " ORDER BY totale DESC"
        ).fetchall()

    def sum_produttore_unita(self):
        """
        Somma pesi raggruppata per produttore + unità locale combinati.
        Usata nel Riepilogo come tabella unica al posto delle due separate.
        """
        return self._conn.execute(
            "SELECT produttore, indirizzo AS ul, SUM(peso) totale"
            " FROM records"
            " GROUP BY produttore, indirizzo"
            " ORDER BY totale DESC"
        ).fetchall()

    def sum_destinatario(self):
        return self._conn.execute(
            "SELECT destinatario, SUM(peso) totale"
            " FROM records"
            " GROUP BY destinatario"
            " ORDER BY totale DESC"
        ).fetchall()

    def sum_codice_err(self):
        """
        Restituisce la somma dei pesi raggruppata per codice ERR.

        Usata nella pagina "Riepilogo" per la tabella destra.
        """
        return self._conn.execute(
            "SELECT codice_err, SUM(peso) totale"
            " FROM records"
            " GROUP BY codice_err"
            " ORDER BY totale DESC"
        ).fetchall()

    def total(self):
        """
        Restituisce la somma totale di tutti i pesi in kg.

        Se non ci sono record, SUM() restituisce NULL → il codice
        lo converte in 0.0 con "or 0.0" per evitare errori.

        Usata nel pannello centrale della pagina "Riepilogo".
        """
        r = self._conn.execute("SELECT SUM(peso) s FROM records").fetchone()
        return r["s"] or 0.0

    def count(self):
        """
        Restituisce il numero totale di record presenti nel database.

        Usato per aggiornare il contatore mostrato nell'interfaccia
        (es. "12 record inseriti").
        """
        return self._conn.execute(
            "SELECT COUNT(*) c FROM records"
        ).fetchone()["c"]
