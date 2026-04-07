COCKPIT TRANSFER - PORTABLE USE

This folder can be entirely copied to another Windows PC or Mac.

Quick Structure:

- `launch-cockpit-transfer.bat`: Quick GUI launch on Windows
- `export-fast.bat`: Quick export of all emails found on all providers
- `import-fast.bat`: Automatically imports the latest available ZIP and then restarts Cockpit Tools
- `macos_launchers/`: Folder with all launchers to open on macOS
- `cockpit_transfer/`: App code
- `app_state.json`: Local app memory, created automatically

To use it:

1. Copy the entire `cockpit-transfer` folder.
2. On the destination PC open:
   - Windows: `launch-cockpit-transfer.bat`
   - macOS: `macos_launchers/launch-cockpit-transfer.command`

Quick Workflow:

1. On the source PC run:
   - Windows: `export-fast.bat`
   - macOS: `macos_launchers/export-fast.command`
2. Pass the newly created ZIP in `Downloads` to the destination PC.
3. On the destination PC run:
   - Windows: `import-fast.bat`
   - macOS: `macos_launchers/import-fast.command`

Requirements:

- Windows or macOS
- Python 3 installed and available as `py`, `python3` or `python`

Notes:

- Primary paths are automatically detected for the current user:
  - Windows: `%USERPROFILE%\.antigravity_cockpit`, `%USERPROFILE%\.codex`, `%USERPROFILE%\.gemini`
  - macOS: `~/.antigravity_cockpit`, `~/.codex`, `~/.gemini`
- The app remembers the last email set, chosen providers, and the last imported file in `app_state.json`.
- `export-fast.bat` ignores the GUI email box and automatically takes all detected emails across Codex, Gemini, and Antigravity.
- `import-fast.bat` first searches for the latest `.zip` in `Downloads`; if not found, it uses the last file saved in `app_state.json`.
- On macOS, use the launchers inside `macos_launchers/`.
- After `import-fast.bat`, Cockpit Tools is closed and reopened automatically when the local launcher is available.
- The ZIP created in export contains both `.bat` scripts for Windows and scripts for macOS.
- Import accepts the same ZIP even if it was created or re-compressed on macOS or Windows, including cases with wrapper folders or typical macOS metadata (`__MACOSX`, `._*`, `.DS_Store`).
- If you copy this folder to another PC, the app continues using the paths of the new local user.
- On macOS, `.command` launchers automatically try to remove quarantine and restore executable permissions; if the system still blocks scripts, run `macos_launchers/0-mac-fix-permissions-and-launch.command` once.
