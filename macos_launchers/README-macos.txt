MACOS

On Mac, you don't need a different version of the app: you must copy the entire `cockpit-transfer` folder.

For simplicity, the files to open on macOS are collected here:

- `launch-cockpit-transfer.command`: Opens the GUI
- `export-fast.command`: Creates the export ZIP
- `import-fast.command`: Imports the latest found ZIP
- `0-mac-fix-permissions-and-launch.command`: Tries to remove macOS quarantine and then starts the app

These launchers work on the parent folder, so do not move the `.command` files by themselves: they must remain inside the complete app folder.
