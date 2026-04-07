TRANSFERIMENTO COCKPITS - USO PORTABILE

Questa cartella si puo copiare interamente su un altro PC Windows o Mac.

Struttura rapida:

- `avvia-transferimento-cockpits.bat`: avvio rapido GUI su Windows
- `export_fast.bat`: export rapido di tutte le mail trovate su tutti i provider
- `import_fast.bat`: importa automaticamente l'ultimo ZIP disponibile e poi riavvia Cockpit Tools
- `macos\`: cartella con tutti i launcher da aprire su macOS
- `avvia-transferimento-cockpits.command`: avvio rapido GUI su macOS, mantenuto in root per compatibilita`
- `export_fast.command`: export rapido cliccabile su macOS, mantenuto in root per compatibilita`
- `import_fast.command`: import rapido cliccabile su macOS, mantenuto in root per compatibilita`
- `avvia-transferimento-cockpits.sh`: avvio rapido GUI da shell
- `export_fast.sh`: export rapido da shell
- `import_fast.sh`: import rapido da shell
- `transferimento_cockpits\`: codice app
- `app_state.json`: memoria locale dell'app, viene creato automaticamente

Per usarla:

1. Copia tutta la cartella `transferimento-cockpits`
2. Sul PC di destinazione apri:
   - Windows: `avvia-transferimento-cockpits.bat`
   - macOS: `macos/avvia-transferimento-cockpits.command`
   - shell: `./avvia-transferimento-cockpits.sh`

Workflow rapido:

1. Sul PC sorgente esegui:
   - Windows: `export_fast.bat`
   - macOS: `macos/export_fast.command`
   - shell: `./export_fast.sh`
2. Passa al PC di destinazione lo ZIP appena creato in `Downloads`
3. Sul PC di destinazione esegui:
   - Windows: `import_fast.bat`
   - macOS: `macos/import_fast.command`
   - shell: `./import_fast.sh`

Requisiti:

- Windows o macOS
- Python 3 installato e disponibile come `py`, `python3` oppure `python`

Note:

- I percorsi principali vengono rilevati automaticamente per l'utente corrente:
  - Windows: `%USERPROFILE%\.antigravity_cockpit`, `%USERPROFILE%\.codex`, `%USERPROFILE%\.gemini`
  - macOS: `~/.antigravity_cockpit`, `~/.codex`, `~/.gemini`
- L'app ricorda ultimo set email, provider scelti e ultimo file importato dentro `app_state.json`.
- `export_fast.bat` ignora il box email della GUI e prende automaticamente tutte le mail rilevate tra Codex, Gemini e Antigravity.
- `import_fast.bat` cerca prima l'ultimo `.zip` in `Downloads`; se non lo trova usa l'ultimo file salvato in `app_state.json`.
- Su macOS usa preferibilmente i launcher dentro `macos/`; i corrispondenti file `.command` in root restano solo per compatibilita`.
- Dopo `import_fast.bat`, Cockpit Tools viene chiuso e riaperto automaticamente quando il launcher locale e` disponibile.
- Lo ZIP creato in export contiene sia gli script `.bat` per Windows sia gli script `.command` e `.sh` per macOS/shell.
- L'import accetta lo stesso ZIP anche se e` stato creato o ricompresso su macOS o Windows, inclusi i casi con cartella contenitore o metadata tipici macOS (`__MACOSX`, `._*`, `.DS_Store`).
- Se copi questa cartella su un altro PC, l'app continua a usare i percorsi del nuovo utente locale.
- Su macOS, i launcher `.command` provano da soli a togliere la quarantena e a rimettere i permessi eseguibili; se il sistema blocca comunque gli script, esegui una volta `macos/0-mac-fix-permissions-and-launch.command`.
