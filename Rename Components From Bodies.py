"""Sync component names with their body names.
Version 1

Run this from the TOP-LEVEL assembly (not while editing a sub-component).
Press Escape first if you are in component edit mode.

Strategy:
  1. Scan the timeline backwards to find the last point where the most
     root-level bodies are visible (just before "Create Component from Body").
  2. Fingerprint each root body by its bounding box (position + size).
  3. Roll forward to end.
  4. For each sub-component body, compute the same fingerprint and look up
     the correct name in the map built in step 2.
  5. Rename the component (and body) to the correct name.

Works across designs — no hardcoded timeline index.
"""

import re
import traceback
import adsk.core
import adsk.fusion

app = adsk.core.Application.get()
ui = app.userInterface

PREVIEW_ONLY = False  # Set to True to preview without making changes
DECIMAL_PLACES = 2    # Rounding precision for fingerprint (cm)


def fingerprint(body):
    """Unique key based on bounding box min/max coordinates."""
    try:
        bb = body.boundingBox
        r = DECIMAL_PLACES
        return (
            round(bb.minPoint.x, r), round(bb.minPoint.y, r), round(bb.minPoint.z, r),
            round(bb.maxPoint.x, r), round(bb.maxPoint.y, r), round(bb.maxPoint.z, r),
        )
    except:
        return None


def base_name(name):
    return re.sub(r'\s*\(\d+\)', '', name).strip()


def find_best_rollback_index(tl, root):
    """
    Scan the timeline backwards to find the index just before bodies were
    moved into sub-components. We look for the position that maximises the
    number of root-level bodies visible.

    Returns (best_index, body_count) or (None, 0) if nothing useful found.
    """
    total = tl.count
    # Current body count at end of timeline (usually 0 after conversion)
    end_count = root.bRepBodies.count

    # Sample a handful of positions near the end to find the jump
    # We scan backwards in steps, then narrow down
    best_index = None
    best_count = end_count

    step = max(1, total // 20)  # sample ~20 points
    candidates = list(range(total - 2, max(0, total - 100), -step))
    candidates += list(range(total - 2, max(0, total - 20), -1))  # fine scan near end
    candidates = sorted(set(candidates), reverse=True)

    for idx in candidates:
        try:
            tl.item(idx).rollTo(rollBefore=False)
            adsk.doEvents()
            cnt = root.bRepBodies.count
            if cnt > best_count:
                best_count = cnt
                best_index = idx
                if cnt == tl.count - 1:
                    break  # found all bodies, no need to scan further
        except:
            continue

    return best_index, best_count


def run(_context: str):
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('No active Fusion design found.')
            return

        import os, subprocess
        adsk.doEvents()

        root = design.rootComponent
        tl = design.timeline
        lines = []
        lines.append(f'Root: "{root.name}"')
        lines.append(f'Timeline items: {tl.count}')
        lines.append(f'Mode: {"PREVIEW ONLY" if PREVIEW_ONLY else "APPLYING RENAMES"}')
        lines.append('')

        # ── Step 1: Find the best rollback point automatically ──
        lines.append('Scanning timeline for best rollback point...')
        best_index, best_count = find_best_rollback_index(tl, root)

        if best_index is None or best_count == 0:
            tl.moveToEnd()
            adsk.doEvents()
            ui.messageBox(
                'Could not find a timeline position where bodies are visible at root level.\n\n'
                'Make sure you are running this from the top-level assembly and that '
                '"Create Component from Body" has already been run.'
            )
            return

        lines.append(f'Best rollback index: [{best_index}]  bodies visible: {best_count}')
        lines.append('')

        # ── Step 2: Roll to best index, capture fingerprint → correct name ──
        fp_to_name = {}
        try:
            tl.item(best_index).rollTo(rollBefore=False)
            adsk.doEvents()
            fp_collisions = 0
            for i in range(root.bRepBodies.count):
                b = root.bRepBodies.item(i)
                fp = fingerprint(b)
                if fp is None:
                    lines.append(f'  [{i:02d}] "{b.name}"  fingerprint FAILED')
                    continue
                if fp in fp_to_name:
                    fp_collisions += 1
                else:
                    fp_to_name[fp] = b.name
            lines.append(f'Captured {len(fp_to_name)} unique fingerprints  ({fp_collisions} collisions)')
        except Exception as e:
            lines.append(f'ERROR at rollback: {e}')
        finally:
            try:
                tl.moveToEnd()
                adsk.doEvents()
            except Exception as e2:
                lines.append(f'ERROR restoring timeline to end: {e2}')

        lines.append(f'Restored to end.')
        lines.append('')

        if not fp_to_name:
            lines.append('No fingerprints captured — cannot rename.')
            out_path = os.path.expanduser('~/Desktop/fusion_rename_debug.txt')
            with open(out_path, 'w') as f:
                f.write('\n'.join(lines))
            subprocess.run(['open', out_path])
            ui.messageBox('No fingerprints captured. See debug file.')
            return

        # ── Step 3: Match sub-component bodies by fingerprint ──
        lines.append('=== RESULTS ===')
        to_rename = []
        already_correct = []
        no_match = []

        seen_comps = set()
        for occ in root.allOccurrences:
            comp = occ.component
            tok = comp.entityToken
            if tok in seen_comps:
                continue
            seen_comps.add(tok)

            if comp.bRepBodies.count == 0:
                no_match.append(f'  comp="{comp.name}" (no bodies)')
                continue

            b = comp.bRepBodies.item(0)
            fp = fingerprint(b)
            correct_name = fp_to_name.get(fp)

            if correct_name is None:
                no_match.append(f'  comp="{comp.name}"  (no fingerprint match)')
            elif comp.name == correct_name:
                already_correct.append(f'  comp="{comp.name}"  ✓')
            else:
                to_rename.append((comp, b, correct_name))
                lines.append(f'  RENAME: "{comp.name}"  →  "{correct_name}"')

        lines.append('')
        lines.append(f'Components to rename:  {len(to_rename)}')
        lines.append(f'Already correct:       {len(already_correct)}')
        lines.append(f'No fingerprint match:  {len(no_match)}')

        if no_match:
            lines.append('')
            lines.append('--- No match (will not be renamed) ---')
            lines.extend(no_match)

        # ── Step 4: Apply or preview ──
        if not PREVIEW_ONLY and to_rename:
            lines.append('')
            lines.append('=== APPLYING RENAMES ===')
            errors = []
            success = 0
            for comp, body, correct_name in to_rename:
                try:
                    old = comp.name
                    comp.name = correct_name
                    body.name = correct_name
                    lines.append(f'  ✓ "{old}"  →  "{correct_name}"')
                    success += 1
                except Exception as e:
                    errors.append(f'  ✗ "{comp.name}": {e}')
            lines.extend(errors)
            lines.append('')
            lines.append(f'Done. Renamed {success}/{len(to_rename)} component(s).')
        elif PREVIEW_ONLY:
            lines.append('')
            lines.append('PREVIEW ONLY — no changes made.')
            lines.append('Set PREVIEW_ONLY = False at the top of the script to apply.')

        out_path = os.path.expanduser('~/Desktop/fusion_rename_debug.txt')
        with open(out_path, 'w') as f:
            f.write('\n'.join(lines))
        subprocess.run(['open', out_path])

        if PREVIEW_ONLY:
            summary = (
                f'PREVIEW — no changes made.\n\n'
                f'Would rename:    {len(to_rename)}\n'
                f'Already correct: {len(already_correct)}\n'
                f'No match:        {len(no_match)}\n\n'
                f'Set PREVIEW_ONLY = False and re-run to apply.'
            )
        else:
            summary = (
                f'Done!\n\n'
                f'Renamed:         {success}/{len(to_rename)}\n'
                f'Already correct: {len(already_correct)}\n'
                f'No match:        {len(no_match)}\n\n'
                f'See ~/Desktop/fusion_rename_debug.txt for details.\n'
                f'Ctrl+Z to undo if anything looks wrong.'
            )
        ui.messageBox(summary)

    except:
        ui.messageBox('Error — attempting to restore timeline...')
        try:
            design.timeline.moveToEnd()
        except:
            pass
        app.log(f'Failed:\n{traceback.format_exc()}')
