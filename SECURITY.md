# Contratto operativo di mistermif AI

## Area autonoma

L'assistente può creare, modificare, testare e ripristinare liberamente soltanto
i file contenuti nella cartella dedicata `mistermif_ai`.

## Modifiche esterne

Qualsiasi modifica fuori dalla cartella dedicata richiede sempre una conferma
esplicita dell'utente. Prima di chiederla, l'assistente deve indicare:

- il motivo della modifica;
- i file o le configurazioni coinvolti;
- i rischi e gli effetti previsti;
- il backup disponibile e la procedura di ripristino.

La conferma non può essere memorizzata come autorizzazione permanente.

## Azioni operative

Le azioni operative già inserite nella lista consentita, come spegnere il clima
per proteggere la colonnina, possono essere autonome quando l'interruttore
generale è attivo. L'interruttore le blocca immediatamente lato server.

## Notifiche

L'assistente può inviare notifiche senza conferma esclusivamente attraverso il
servizio `notify.*` configurato nelle opzioni dell'add-on. Il nome del servizio
non può essere scelto dinamicamente da una conversazione.

## Autoriparazione

Le correzioni vengono preparate e provate nella cartella dedicata. Se una
correzione richiede una modifica esterna, resta in attesa della conferma descritta
sopra. Firmware, BMS e protezioni elettriche non sono autoriparabili.
