# Note validation - local persistence fallback - 2026-11-19

This record covers the Note app (`com.ohos.note`) white-screen investigation,
the board-side workaround, and the unified-build wiring. The Note HAP was
hot-installed and verified on the board. No complete image was built or flashed
for this work.

## Board state

- Target: `10.43.9.213:5555`
- boot_id: `00836ef8-c49c-4a6e-8c58-a0bf1da68998`
- Kernel: `6.1.83-rdkhm #5` (2026-11-19 16:13 CST)
- The board was running the previous development image plus hot-installed HAPs;
  the exact board-side image SHA256 was not read back.
- Note HAP was installed with `bm install -r` and is under
  `/data/app/el1/bundle/public/com.ohos.note`.

## Symptoms

Before the fix, `com.ohos.note` had a process and a focused `note0` window, but
the window was white with a loading spinner. The app logged:

```text
MyNoteHomeComp_Tablet: db has created
MyNoteHomeComp_Tablet: onPageShow
```

The database was an empty SQLite file:

```text
/data/app/el2/100/database/com.ohos.note/default/rdb/note.db
4096 bytes, schema 0, no tables
```

`MyNoteHome` only renders its content when `DBQueryFinished == 1`. The app found
the existing empty database, called `RdbStoreUtil.initAppStorage()`, and then
never set the flag because the RDB open/query callback did not return.

## Root causes

### 1. Empty RDB database is never repaired

The empty `note.db` caused the initial query to fail, but the asynchronous
failure was not handled. Because the file existed, the app did not call
`createRdbStore()` to create the schema. The page stayed blank.

The app was changed to keep an independent local JSON store so an unavailable
database cannot block the UI or lose edits.

### 2. RDB open callback does not return on this board

The system `distributeddata` service is alive, but the Note RDB open callback
never completed. The board logged only the connection creation:

```text
Rdb ConnectionPool[Create]: ...
```

There was no `initAppStorage, store is ...` log and no table creation. Changing
Note from the Promise form to the callback form did not help. The launcher also
reported repeated RDB query errors on the same board, so this is a system RDB
path issue rather than a Note-only database schema problem.

The ArkTS RDB wrapper uses `taskpool.execute(getRdbStoreSync, ...)` for both
`getRdbStore()` forms:

`foundation/distributeddatamgr/relational_store/frameworks/js/ani/relationalstore/ets/@ohos.data.relationalStore.ets`

This remains the prime suspect for the missing callback. It was not patched in
this session because that requires a system image change.

### 3. `Web` component is unavailable

Once the UI was allowed to render, it crashed with:

```text
ReferenceError: Web is not defined
```

The crash came from `NoteContentComp.initialRender()` and its `Web` editor. The
current image does not provide the ArkUI `Web` component. The content editor was
replaced with a `TextArea` fallback so Note can open and edit text.

Fault log:
`/data/log/faultlog/faultlogger/jscrash-com.ohos.note-20010017-20261119185407515.log`

## Changes

Patch: `patches/haps/notes-db-init.patch`

SHA256: `9a17b95d300860a6d728831d42b080e0f4f6487fe3dcc3d963642ec03e2c98a8`

### `RdbStoreUtil.ets`

- Added a JSON store at `filesDir/notes.json`.
- `loadLocalData()` restores folders and notes on startup.
- `saveLocalData()` writes the current AppStorage arrays.
- `insert()`, `update()`, and `delete()` persist the current arrays when
  `rdbStore` is unavailable.
- `saveNote()` updates the selected note and persists it immediately.
- Default system folders/notes are used when no local file exists.
- The legacy RDB paths remain in the file as unused helpers for a future system
  RDB fix.

### `GlobalResourceManager.ets`

- Replaced the module-level `getContext(this)` capture with a lazy
  `AppStorage('noteContext')` lookup.
- Missing context now resolves an empty string instead of leaving the Promise
  unresolved.

### `NoteContentComp.ets`

- Replaced the unavailable `Web` editor with a `TextArea`.
- `onChange` updates `content_text` and calls `RdbStoreUtil.saveNote()`.
- This is a functional fallback, not a rich-text editor.

## Board verification

Local data file:

```text
/data/app/el2/100/base/com.ohos.note/haps/default/files/notes.json
```

Verification sequence:

1. Started Note and confirmed the folder list, note list, and content area.
2. Opened `UX会议纪要`, entered full-screen content, and typed `PERSIST_TEST`.
3. Confirmed the string was written to `notes.json`.
4. Ran `aa force-stop com.ohos.note` and started the app again.
5. Confirmed the log:

```text
RdbStoreUtil: loadLocalData success, notes: 4
```

6. Confirmed the restarted UI still contains `PERSIST_TEST`.

Evidence screenshots:

- `out/board-logs/note-no-web.jpeg` - Note UI after the workaround
- `out/board-logs/note-local-edit2.jpeg` - content edit
- `out/board-logs/note-restart.jpeg` - content retained after restart

The test note `PERSIST_TEST` remains in the board's local app data. Clearing the
Note app data removes the local JSON store and restores defaults.

## Build and image wiring

The unified build now includes Note:

- `config/build/pipeline.json`
  - `haps` stage runs `python3 scripts/build-hap.py notes`.
- `scripts/make-openharmony-image.sh`
  - Injects `out/haps/notes.hap` as
    `/system/app/com.ohos.note/Note.hap`.
- `scripts/verify-openharmony-image.py`
  - Verifies the same Note HAP mapping.
- `config/patches.json`
  - Lists `haps/notes-db-init.patch`.

Current Note artifact:

```text
out/haps/notes.hap
SHA256 036227c0f6309871b25cf1b82af3a335edc925b7bf08b38c18c2fea025bda85d
```

Static checks passed:

```text
./rdkhm check
scripts/check-patch-format.py
scripts/check-patch-coverage.py
```

## Later unified build

The unified build was run after this record and produced:

```text
out/images/rdkhm-x5-openharmony-dev.img
SHA256 db0a75bbda4bf3ccc61e57d4cb90699624144b6824cd0d1ca09e4901439dbd78
```

The board now reports boot_id `9ade3a96-6eb4-4876-a3dc-f407990d6b5e`, and
`/system/app/com.ohos.note/Note.hap` matches the current HAP:
`036227c0...` (2,634,753 bytes, 2026-11-19 20:54). The exact board image
SHA256 was not read back.

That boot is not yet a successful Note validation. The screen is black, the
Launcher is not running, and `bm dump -n com.ohos.note` / `com.ohos.launcher`
fail because BMS has no installed bundle information. Only SystemUI windows
are present and WindowManager reports `Focus window: 0`.

Evidence: `out/board-logs/now2.jpeg`

## On-board repair attempt

The board was not rebooted. `accountmgr` (pid `953`) was killed so init could
restart it. The replacement process (`4174`) logged `ActivateDefaultOsAccount`,
the user-100 start event and `SendToAMSAccountStart`, but the failure below
persisted:

```text
AccountMgr: service ptr is null!
BMS: GetForegroundOsAccountLocalId failed ret:4194341
```

Manual Launcher install/start also failed:

```text
bm install -p /system/app/com.ohos.launcher/Launcher.hap -u 100
code:301 user not exist.

bm install -p /system/app/com.ohos.launcher/Launcher.hap -u 0
code:9568292 zero user can only install singleton app.

aa start -b com.ohos.launcher -a com.ohos.launcher.MainAbility -U 100
10104001 The specified ability does not exist
```

The BMS state explains the install failure:

```text
bootevent.bms.main.bundles.ready = true
installed_bundle rows = 37
preinstalled_bundle rows = 38
bundle_user_info.json is empty
```

BMS has the system bundle records, but no user bundle association and no
foreground user. Only SystemUI is running. The current image also has no
`com.ohos.sceneboard` directory or process, but the earlier recovery image and
the previous image also lacked it, so SceneBoard absence is not sufficient by
itself to explain this boot.

This cannot be repaired by the current board-only install commands because
`bm` only accepts the current foreground user or user 0, and the foreground
user lookup fails. A reboot may give BMS a second preinstall pass now that the
user-100 account exists, but that needs explicit approval. Otherwise the image
needs a BMS/account first-boot fix and a cold-boot retry.

## Known limitations

- System RDB is still broken; `note.db` remains an empty file and is not used by
  this fallback.
- Note data is app-local JSON, not the relational database.
- The editor is a plain `TextArea`; HTML content such as the built-in sample notes
  is shown as raw markup.
- Rich formatting, images, and Web-backed editor behavior are not available.
- Cold boot of an image containing the new Note HAP is not validated.

## Follow-up

1. Fix or replace the system RDB path, then restore database-backed Note data.
2. Restore the Web editor when the image provides the ArkUI Web component.
3. Run the unified build, verify Note HAP injection, and cold-boot test the image.
