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

Le automazioni dinamiche create dall'assistente possono operare senza conferma
per singola azione soltanto quando apparati, servizi, direzione del comando e
limiti sono già presenti in una policy approvata. La proprietà dell'automazione
non autorizza automaticamente un nuovo apparato o una nuova categoria di azione.

Ogni decisione deve registrare input, regola, motivazione, azione, esito e
versione dell'automazione. Devono essere disponibili disattivazione immediata e
rollback.

## Notifiche

L'assistente può inviare notifiche senza conferma esclusivamente attraverso il
servizio `notify.*` configurato nelle opzioni dell'add-on. Il nome del servizio
non può essere scelto dinamicamente da una conversazione.

## Privacy

La modalità predefinita è `local_only`: nessun contenuto viene inviato a un
modello cloud. La modalità `redacted_cloud` è opzionale e filtra coordinate,
tracker, contatti, indirizzi di rete, token e categorie di memoria locali prima
della richiesta esterna.

Viaggi, campeggi, piazzole, profilo del mezzo, contatti e abitudini restano
sempre esclusi dal contesto cloud. Il filtro è una misura di riduzione del
rischio; la garanzia più forte resta l'elaborazione interamente locale.

## Autoriparazione

Le correzioni vengono preparate e provate nella cartella dedicata. Se una
correzione richiede una modifica esterna, resta in attesa della conferma descritta
sopra. Firmware, BMS e protezioni elettriche non sono autoriparabili.

## Persone e animali

Le modalità che tutelano persone o animali devono usare controlli locali
deterministici e sensori ridondanti. L'AI può prevedere, coordinare e notificare,
ma non è l'unico livello di sicurezza.

In modalità animali a bordo il climatizzatore autorizzato è un carico prioritario.
Una logica di risparmio energetico non può spegnerlo in autonomia. Se energia,
temperatura o funzionamento del clima diventano incerti, l'assistente deve
avvisare in anticipo, aumentare la priorità e richiedere intervento umano.
