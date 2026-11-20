# Patch contract

Every file tracked here is a minimal patch against a pinned upstream revision.
`config/patches.json` is the only manifest; `scripts/apply-patches.py` is the
only applier. Do not apply these files by hand and do not add unlisted files.

## Naming and layout

- `patches/<subsystem>/NNNN-short-name.patch`, zero-padded and ordered.
- Kernel patches live under `patches/kernel/`; RT-only patches live under
  `patches/optional/preempt-rt/` and are applied only by the `rt` profile.
- `patches/nearlink-bsp/` and `patches/nearlink-ssap/` are applied by their
  prepare scripts and are declared in the manifest `globs` section.

## File format

- UTF-8, LF only, one trailing newline. CRLF is rejected.
- Every patch starts with a mail header and a DCO sign-off:

```text
From: wentywenty <2321901849@qq.com>
Subject: [PATCH] <path relative to patches/>

Signed-off-by: wentywenty <2321901849@qq.com>
---
<diff>
```

- Use a plain diff (`--- a/...` / `+++ b/...`, no `diff --git` or `index`
  lines) unless the patch needs git metadata.
- Use the git-style diff (`diff --git` and `index`, preserving `new file mode`,
  `deleted file mode`, `rename`, `similarity index` or binary metadata) when
  file creation, deletion, rename, mode or binary content is involved.
- The two styles are mutually exclusive per file: a patch that needs metadata
  keeps git-style sections for the whole patch.

Upstream files that still use CRLF on disk require `"ignore_whitespace": true`
in the manifest entry; the patch file itself remains LF.

## Validation

```sh
python3 scripts/check-patch-coverage.py   # manifest coverage, no orphans
python3 scripts/check-patch-format.py     # LF, header, sign-off, diff style
python3 scripts/apply-patches.py --dry-run
./rdkhm check
```
