# Rename Components From Bodies

A Fusion 360 script that automatically renames components to match their original body names after using the **Create Component from Body** command.

When Fusion 360 converts bodies into components, the resulting components are often given generic names. This script scans your design timeline to recover the original body names and applies them back to the components.

## How It Works

1. Scans the timeline backwards to find the point where the most root-level bodies were visible (just before they were converted into components)
2. Fingerprints each body using its bounding box coordinates
3. Rolls the timeline back to the end
4. Matches each sub-component's body to the fingerprint map and renames accordingly

## Installation

1. Open Fusion 360
2. Go to **Utilities → Add-Ins → Scripts and Add-Ins**
3. Click the green **+** icon next to **My Scripts**
4. Navigate to the folder containing this script and select it

## Usage

1. Open the design you want to fix
2. Make sure you are at the **top-level assembly** — press **Escape** first if you are in component edit mode
3. Go to **Utilities → Add-Ins → Scripts and Add-Ins**
4. Select **Rename Components From Bodies** and click **Run**
5. A summary dialog will appear showing what was renamed
6. A detailed log is saved to `~/Desktop/fusion_rename_debug.txt`
7. Use **Ctrl+Z** to undo if anything looks wrong

## Options

At the top of the script file you can adjust two settings:

| Setting | Default | Description |
|---|---|---|
| `PREVIEW_ONLY` | `False` | Set to `True` to see what would be renamed without making any changes |
| `DECIMAL_PLACES` | `2` | Rounding precision (in cm) used for body fingerprinting |

## Requirements

- Autodesk Fusion 360
- The design must have been created using **Create Component from Body**
- Run from the top-level assembly (not while editing a sub-component)

## Supported OS

Windows, macOS
