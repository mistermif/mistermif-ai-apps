# Changelog

## 1.5.5

- Rimosso il limite di 80 entità dall'inventario locale di Home Assistant.
- L'assistente può ora indicizzare tutte le entità e selezionare dinamicamente
  soltanto quelle pertinenti alla richiesta o al monitoraggio in corso.
- Il limite configurabile resta applicato esclusivamente al contesto destinato
  al modello AI, evitando invii massivi e consumo inutile di token.
- Estesa la lettura locale in sola osservazione a tutti i domini Home Assistant,
  senza ampliare in alcun modo i permessi di comando.
- Rafforzati i filtri di privacy per IP pubblico, SSID, BSSID, MAC, token,
  credenziali e parametri protetti.
- Le impostazioni mostrano separatamente inventario HA locale e limite massimo
  del contesto AI.

## 1.5.4

- Aggiunta la base o rimessaggio all'intervista iniziale, usando il GPS corrente e un raggio configurabile.
- Corretto il falso avvio dei viaggi causato dalla deriva GPS a veicolo fermo.
- La partenza richiede ora più campioni coerenti e almeno 100 metri di spostamento reale fuori dalla base.
- I piccoli spostamenti GPS da fermo non incrementano più i chilometri.
- Aggiunto nelle impostazioni il comando confermato per eliminare un viaggio rilevato per errore.

## 1.5.3

- Aggiunti ricerca soste, diario di viaggio ed esportazioni CSV/GPX.
- Migliorata la lettura della posizione GPS e il contesto fornito all'assistente.
