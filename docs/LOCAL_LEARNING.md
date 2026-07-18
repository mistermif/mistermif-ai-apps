# Apprendimento locale

## Obiettivo

Mistermif AI apprende abitudini e risultati senza addestrare autonomamente un
modello remoto e senza inviare lo storico completo fuori dalla caravan.

## Cosa apprende

- orari ricorrenti di cucina, boiler, clima e ricarica;
- consumi tipici e risorse necessarie prima di un'attività;
- preferenze di temperatura e comfort;
- rendimento di frigorifero, ventole e fotovoltaico;
- comportamento energetico nei diversi campeggi;
- orari di partenza, sosta e rientro;
- efficacia dei consigli e correzioni dell'utente.

## Routine predittive

Una routine viene proposta soltanto dopo osservazioni ripetute. Esempio: se la
cucina a induzione viene usata regolarmente intorno alle 12, il copilota può
verificare in anticipo SOC, produzione, ricarica, carichi differibili e limite
della colonnina. La preparazione non deve creare consumi inutili quando
l'attività prevista non avviene.

Ogni abitudine conserva contesto, giorni, finestra oraria, numero di osservazioni,
confidenza e ultima conferma. L'utente può sospenderla, correggerla o cancellarla.

## Ciclo di apprendimento

1. registra situazione, decisione e risultato;
2. cerca schemi su più episodi comparabili;
3. formula un'ipotesi con livello di confidenza;
4. la prova sui dati storici;
5. la esegue in modalità ombra senza comandare apparati;
6. propone o attiva l'adattamento entro margini già autorizzati;
7. misura l'esito e mantiene il rollback.

Un singolo episodio non diventa automaticamente una regola.

## Limiti

L'apprendimento può affinare avvisi, tempi, isteresi e valori non critici entro
intervalli approvati. Non può ampliare gli apparati controllati, rimuovere vincoli
rigidi o modificare inverter, BMS, firmware e protezioni elettriche.

Per persone e animali può soltanto anticipare o rafforzare le protezioni, mai
indebolirle.
