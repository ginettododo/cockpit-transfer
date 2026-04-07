# Cockpit Transfer

Transferimento Cockpits is a tool designed to easily package and transfer login tokens and profiles of desktop AI apps (like Codex, Gemini, Antigravity) between different computers. 

## Features

- **Multi-Product Support**: Export data specifically for Codex, Gemini, and Antigravity.
- **Easy Selection**: Choose specific email profiles to transfer.
- **Preview & Inspection**: Check exactly what's being packaged and its status across providers.
- **One-Click Bundles**: Creates a secure, portable ZIP bundle of the profiles, ready to be sent to another computer.
- **One-Click Imports**: Effortlessly import profiles that were packaged from another computer.
- **Options**: Manage profile activation natively without replacing local configs completely.

## Important Note

**Security Notice:** The exported bundles contain **live credentials**. Treat them just like passwords and be careful where you store and share them!

## Getting Started

1. Set up the local environment and dependencies using `{uv}` or by directly executing the scripts on supported platforms.
2. Launch the app using one of the pre-configured launcher scripts:
   - macOS / Linux: `avvia-transferimento-cockpits.command` or `avvia-transferimento-cockpits.sh`
   - Windows: `avvia-transferimento-cockpits.bat`
3. Enter the emails you wish to export in the "Transfer" tab.
4. Select the providers you want to target (Codex, Gemini, Antigravity).
5. Click **"Crea ZIP"** (Create ZIP) to generate the secure package.
6. Transfer the ZIP to your target machine, then open this app again and use the **"Importa"** tab to load the profiles.

## Developer & Internal

The project provides an intuitive **Tkinter-based GUI** for ease of use, as well as command-line functionalities. The modular architecture (`bundle.py`, `gui.py`, `multi_transfer.py`, `runtime_support.py`) ensures that reading, replacing, extracting and restarting different product cockpits flows seamlessly.

## License & Ownership

Developed for internal management and tool portability. Use responsibly.
