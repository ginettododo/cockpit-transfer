# Todo

- [x] Analizzare launcher, path runtime e flusso ZIP attuali
- [x] Rendere l'import ZIP robusto a bundle creati o ricompressi su Windows e macOS
- [x] Aggiungere launcher semplici anche per macOS per GUI, export rapido e import rapido
- [x] Aggiornare la documentazione portabile con i nuovi entrypoint e il comportamento cross-platform
- [x] Verificare con controlli CLI non distruttivi, inclusi ZIP con struttura simulata macOS/Windows
- [x] Raggruppare in `macos/` i launcher dedicati a macOS e chiarire cosa va passato sul Mac

# Review

- `py -3 -m compileall transferimento_cockpits main.pyw` passato.
- `py -3 -m transferimento_cockpits export-fast --dry-run` passato: trovato l'insieme email corrente e generato il percorso ZIP atteso in `Downloads`.
- `py -3 -m transferimento_cockpits import-fast --dry-run --no-restart-cockpit --package <windows-like.zip>` passato con ZIP sintetico contenente `transfer-package.json` in root.
- `py -3 -m transferimento_cockpits import-fast --dry-run --no-restart-cockpit --package <mac-like.zip>` passato con ZIP sintetico contenente cartella wrapper `bundle/`, metadata macOS `__MACOSX`, file `._*` e `.DS_Store`.
- Aggiunti launcher macOS cliccabili `export_fast.command` e `import_fast.command`, piu` le controparti shell `export_fast.sh` e `import_fast.sh`.
- Aggiornato `README-PORTABLE.txt` per documentare launcher macOS e compatibilita` dello stesso ZIP tra Windows e macOS.
- Aggiunta cartella `macos/` con i launcher da usare su Mac e con `README-macos.txt` per chiarire che va copiata l'intera cartella app, non i soli file `.command`.
- Non ho potuto eseguire un click-test reale dei `.command` su macOS da questa macchina Windows; il comportamento verificato qui copre il parsing Python/CLI e la robustezza dello ZIP, non l'interazione del Finder macOS.
- La cartella corrente non e` inizializzata come repository git, quindi non era disponibile una review tramite `git diff`.
