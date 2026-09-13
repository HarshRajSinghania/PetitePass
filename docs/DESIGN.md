# PetitePass — Design & Threat Model

This document describes how PetitePass is built and what it defends against. It is
the reference for the invariants that security-relevant changes must preserve.

PetitePass is a deliberately boring, local encrypted vault for users who prefer to
trust as little as possible. Its guiding engineering principle is:

> **Maximum security per line of code, dependency, and feature.**

A useful one-line summary of the posture:

> **Small enough to understand, strong enough to distrust everything else.**

Throughout this document, three labels distinguish what is true from what is
planned:

- **Implemented** — present in the current source tree.
- **Design requirement** — a rule that must hold for any change touching the area.
- **Direction** — a possible future change, not yet built. Directions are written
  cautiously and must not be read as guarantees.

* * *

- [1. Design goals and philosophy](#1-design-goals-and-philosophy)
- [2. Non-goals](#2-non-goals)
- [3. Dependency policy](#3-dependency-policy)
- [4. Feature-admission criteria](#4-feature-admission-criteria)
- [5. Architecture](#5-architecture)
- [6. The core invariant: authentication is decryption](#6-the-core-invariant-authentication-is-decryption)
- [7. Cryptography](#7-cryptography)
- [8. Master-password policy](#8-master-password-policy)
- [9. Vault-file operations and durability](#9-vault-file-operations-and-durability)
- [10. Secret lifecycle](#10-secret-lifecycle)
- [11. Filesystem & storage](#11-filesystem--storage)
- [12. Schema evolution](#12-schema-evolution)
- [13. Supply-chain security](#13-supply-chain-security)
- [14. Threat model](#14-threat-model)
- [15. Testing](#15-testing)
- [16. Invariants (do not regress)](#16-invariants-do-not-regress)

* * *

## 1. Design goals and philosophy

The intended user is unusually security-conscious — the person who assumes their
threats are real and wants to audit what they run. Serving that user well does
**not** mean accumulating every possible security mechanism. Complexity is itself
attack surface. PetitePass deliberately prefers a small number of strong,
understandable mechanisms over a large collection of features.

### 1.1 Maximum security per unit of complexity

Every security mechanism has costs: more code, more dependencies, more migration
paths, more failure modes, more platform-specific behavior, more maintenance, and
more that must be audited. A mechanism earns its place only when its reduction in
*realistic* risk justifies that complexity.

The project optimizes, in order, for:

1. large security benefit;
2. low runtime complexity;
3. a small trusted computing base;
4. understandable behavior;
5. explicit failure semantics;
6. strong automated verification.

Saying *no* to a feature is a legitimate security decision, not a shortfall.

### 1.2 Offline is an invariant

PetitePass is not merely "offline-first" — it must be capable of operating
indefinitely on an air-gapped machine. Normal operation must never require an
online account, cloud service, remote API, telemetry, activation, online recovery,
an update server, or synchronization infrastructure.

There is no network code in the application. Introducing networking is a major
architectural change and a threat-model change — never a routine feature addition.
See [invariant 9](#16-invariants-do-not-regress).

### 1.3 Minimize trust

PetitePass assumes the worst about its surroundings:

- the vault file may be stolen;
- backups may be stolen;
- cloud services may be compromised;
- the build/distribution pipeline may be attacked;
- dependencies may become malicious;
- clipboard-history managers may retain secrets;
- the local machine may eventually be compromised.

The design goal is to minimize how many components the user must trust, and to be
honest about the ones that remain (see [§14](#14-threat-model)).

* * *

## 2. Non-goals

PetitePass is **not** trying to become Bitwarden / KeePass / 1Password with every
possible feature. Unless the fundamental design direction changes, the following
are explicit non-goals:

- cloud synchronization;
- hosted accounts;
- telemetry / remote analytics;
- password sharing;
- team / shared vaults;
- browser extensions;
- automatic favicon or network-metadata retrieval;
- online breach checking;
- online recovery;
- a plugin ecosystem;
- a background daemon;
- a built-in web server;
- remote secret storage.

These are not merely "missing features." Avoiding each one removes attack surface,
avoids a new persistent source of truth or long-lived secret, and keeps the threat
model comprehensible. A feature that would require any of them is presumed rejected
until proven otherwise.

* * *

## 3. Dependency policy

Every runtime dependency expands the trusted computing base. The runtime set is
kept deliberately tiny (see `requirements.txt`) and `pip-audit` gates CI.

A new runtime dependency is normally justified only when it:

- provides a security primitive that should not be implemented locally; **or**
- replaces a substantial amount of risky custom code with a mature, well-reviewed
  implementation; **or**
- delivers a benefit that clearly outweighs its supply-chain and maintenance cost.

Do **not** add a dependency merely to save a few lines of ordinary Python. `pip
freeze` is not dependency management.

The converse also holds: **do not roll your own cryptography.** Mature
cryptographic implementations (SQLCipher, and any future KDF library) are strongly
preferred over home-grown primitives. Minimizing dependencies never justifies
re-implementing crypto.

* * *

## 4. Feature-admission criteria

Before adding functionality, apply this checklist. It exists to make rejecting a
feature a normal, defensible outcome.

- Does it materially help the core job of storing and retrieving **local** secrets?
- Does it introduce networking?
- Does it create another persistent source of truth?
- Does it create another long-lived secret?
- Does it add a dependency?
- Does it introduce parsing of untrusted external data?
- Does it require background services or IPC?
- Can its security semantics be explained simply?
- Can its failure modes be tested (against real SQLCipher where relevant)?
- Would *removing* this feature make PetitePass significantly safer without
  significantly reducing its usefulness?

A feature that adds networking, a second source of truth, a new long-lived secret,
or untrusted parsing starts with a strong presumption against it, and must show a
large, concrete benefit to overcome that presumption. Large feature epics should be
decomposed into narrow, independently reviewable changes.

Passing the checklist is possible. Richer credential functionality can stay within
the lightweight philosophy when each piece is *independently* justified — for
example integrated password/passphrase generation (issue #44), and a modestly larger
record (URL, notes, light tagging, and optionally TOTP / history / import — issue
#45). Each such addition is admitted on its own merits, not as a bundle, and must not
casually turn PetitePass into a large personal-information database. Secret-bearing
fields inherit the [secret-lifecycle rules](#10-secret-lifecycle); anything that
parses external files (import) treats that input as hostile.

* * *

## 5. Architecture

```
                         ┌──────────────────────────────────────────┐
   PyQt5 GUI (gui/)      │                core/                     │
 ┌───────────────────┐   │  ┌────────────────────────────────────┐  │
 │ AuthDialog        │──▶│  │ Vault (vault.py)                   │  │
 │ MainWindow        │   │  │  create / open / rekey             │  │
 │ *Dialog widgets   │──▶│  │  backup_to / restore_from          │  │
 └───────────────────┘   │  │  list / get / add / update / delete│  │
        │ calls only      │  └───────────────┬────────────────────┘  │
        │ VAULT.* and      │                 │ binds                  │
        │ pure helpers     │  ┌──────────────▼─────────┐             │
        ▼                   │  │ Password model (peewee)│             │
  strength.py, utils.py     │  └──────────────┬─────────┘             │
  (no vault access)         │  paths.py  ─────┘  credential.py         │
                            └──────────────────────────────────────────┘
                                             │ SQLCipher (pinned pragmas)
                                             ▼
                                    encrypted vault file
```

**Responsibility boundaries**

| Module                | Owns                                                                                  |
| --------------------- | ------------------------------------------------------------------------------------- |
| `core/vault.py`       | The connection, the master password (in memory only), all vault-file operations, CRUD |
| `core/database.py`    | The peewee `Password` schema — an implementation detail of the Vault                  |
| `core/credential.py`  | `Credential`, a **passwordless** domain object used for listing                        |
| `core/paths.py`       | Data directory, file permissions, legacy migration, fsync helpers                     |
| `core/strength.py`    | Master-password policy (length + common list + zxcvbn score)                          |
| `core/utils.py`       | CSPRNG password generation                                                            |
| `gui/*`               | Presentation only — talks to `VAULT.*` and the pure helpers, never to peewee          |

The GUI does not import `peewee` or the `Password` model; all credential access
goes through the `Vault`. The `Vault` is the single **application-level gateway** to
vault persistence and credential operations: it holds the only open connection, it
is the only component that *intentionally* retains the master password for the
duration of an unlocked session, it translates every peewee `DatabaseError` into a
`VaultError`, and it enforces the business rules (name uniqueness, "credential must
exist", not loading ciphertext to list). Transient copies of the master password may
exist in GUI widgets, Python objects, and runtime-managed memory while
authentication or a password change is in progress — see the memory-limitation note
in [§10](#10-secret-lifecycle).

Keeping this gateway thin and singular is what keeps the *application-level* attack
surface auditable. It is not the whole trusted computing base: that still includes
Python, SQLCipher / `sqlcipher3`, peewee, PyQt (where secrets are displayed or
copied), and the operating system. See [invariant 6](#16-invariants-do-not-regress).

* * *

## 6. The core invariant: authentication is decryption

Older versions kept a bcrypt hash of the master password in a sidecar file and
treated "bcrypt matched" as authenticated. That is a second, weaker oracle that can
desynchronize from the SQLCipher key. It has been removed and must not return: no
secondary authentication oracle may ever become authoritative
([invariant 10](#16-invariants-do-not-regress)).

Authentication works like this:

1. `Vault.open(master)` constructs a SQLCipher connection with `master` as the
   passphrase.
2. It runs a **sentinel query** — `SELECT 1 FROM password LIMIT 1`.
   - Resolving the table forces SQLCipher to decrypt page 1, so a wrong key raises
     `DatabaseError` (HMAC failure).
   - Requiring the application table additionally rejects a *hollow* file (a 0-byte
     or empty SQLite file, which SQLCipher would otherwise initialize under any
     key).
3. Only if the sentinel succeeds is the global model bound to the connection. A
   failed unlock never leaves the model pointing at a closed, wrong-key connection.

An empty master password is refused up front (`_require_nonempty`): peewee omits
`PRAGMA key` for a falsy passphrase, which would produce a *plaintext* database. A
NUL byte is refused for the same reason (peewee raises `ValueError` from
`PRAGMA key='%s'`). See [invariant 3](#16-invariants-do-not-regress).

* * *

## 7. Cryptography

- **Library:** SQLCipher 4 via `sqlcipher3` (cross-platform wheels: Linux, macOS,
  Windows), bound through `playhouse.sqlcipher_ext`.
- **Passphrase handling:** the master password reaches SQLCipher only through
  peewee's quote-escaping `passphrase=` / `rekey()` path (`PRAGMA key='%s'` with
  `'` doubled). The application never builds `PRAGMA` statements with its own string
  interpolation — that was the historical injection/corruption bug. See
  [invariant 2](#16-invariants-do-not-regress).
- **Pinned cipher parameters** (set on every connection via `_make_db`, so a future
  library default change cannot silently make old vaults unreadable):

  | Parameter                | Value                |
  | ------------------------ | -------------------- |
  | `cipher_page_size`       | 4096                 |
  | `kdf_iter`               | 256000               |
  | `cipher_hmac_algorithm`  | HMAC_SHA512          |
  | `cipher_kdf_algorithm`   | PBKDF2_HMAC_SHA512   |

  These are the SQLCipher 4 defaults, so vaults created before pinning open
  unchanged.

- **Key stretching vs. UI policy.** SQLCipher's KDF does the cryptographic
  stretching. `strength.py` is a *UI policy* layer (see [§8](#8-master-password-policy))
  and is deliberately independent of the KDF.

**Direction — Argon2id / raw-key vault format (not yet implemented; issue #41).**
A future vault format may derive a high-entropy 256-bit SQLCipher *raw key* with
Argon2id (memory-hard) instead of relying on SQLCipher's PBKDF2, to increase
resistance to offline cracking. This is recorded as a direction, with explicit
caveats:

- the current PBKDF2-HMAC-SHA512 × 256 000 is **not** considered broken;
- changing the KDF is a high-risk cryptographic and migration change;
- it should happen only *after* schema versioning ([§12](#12-schema-evolution)) and
  durability testing ([§15](#15-testing)) are mature;
- it requires explicit vault-format versioning; existing vaults must remain
  recoverable; migration must be atomic and tested ([§9](#9-vault-file-operations-and-durability));
- a raw key must still reach SQLCipher only through a reviewed, injection-safe
  keying path ([invariant 2](#16-invariants-do-not-regress)) — never an ad-hoc
  `PRAGMA` string;
- the complexity/security tradeoff must remain clearly favorable.

Until all of that holds, PetitePass ships PBKDF2 as above.

* * *

## 8. Master-password policy

`strength.py` is a *policy* layer for advice and admission, distinct from the KDF.

**Implemented (current behavior).**

- Minimum length: 12 characters (`MIN_MASTER_LENGTH`).
- Common-password blocklist: the candidate is rejected if it appears in the bundled
  10k-most-common list (`is_common`). This is a common-password list, not a
  breached-credential database.
- zxcvbn is currently a **hard gate**: a score below 3 (`MIN_MASTER_SCORE`) is
  rejected, and the estimate also drives human-readable advice.
- No mandatory character-class ("must contain a symbol") rules.
- **Known defect (issue #37):** the bundled zxcvbn errors on inputs longer than 72
  characters, and the policy layer does not guard against it — so a long passphrase
  is currently rejected/errored by the *policy* even though the encryption layer
  accepts it. This is a bug, not intended behavior.

**Direction (issues #42 / #37).**

- Prefer a **length-first** policy: raise the minimum length and treat length as the
  primary gate (length dominates guessability for the offline-attack threat).
- Keep the common-password blocklist as a meaningful hard rejection.
- Continue to avoid arbitrary composition rules; support long passphrases and
  Unicode.
- Treat zxcvbn as **advisory guidance** rather than an absolute veto.
- **Design requirement:** a strength/estimation library's internal limit must never
  truncate or reject the actual master password that the encryption layer would
  accept. The policy layer must degrade gracefully on inputs the estimator cannot
  score, never crash and never silently shorten the password.

* * *

## 9. Vault-file operations and durability

Any operation that replaces the **authoritative vault file** uses the same
discipline:

```
1. work on a COPY, never the live file in place
2. fsync the copy               (fatal — a failed flush aborts before the commit)
3. os.replace(copy, vault)      (the single atomic commit point)
4. fsync the directory          (best-effort, post-commit)
5. reopen / verify              (post-commit failures are reported distinctly)
```

The underlying property this protocol guarantees:

> **After any failure, exactly one documented master password opens exactly one
> complete, authoritative vault, and no operation reported as successful may
> silently lose committed entries.**

**Rekey (`rekey`)** copies the closed vault to `<vault>.rekey.tmp`, rekeys and
verifies that copy on a fresh connection, then `os.replace`s it in. A crash before
the replace leaves the original under the old key; the temp file is inert garbage
that `open()` deletes. If the post-commit reopen fails, `VaultRotatedError` is
raised (never an auth error) so the UI does not tell the user their current password
was wrong after the key already changed.

**Restore (`restore_from`)** verifies the backup decrypts under the supplied master
*before* touching anything, copies it to `<vault>.restore.tmp`, re-verifies the
copy, then `os.replace`s it in. Post-commit reopen failure raises
`VaultRestoredError`. A leftover `.restore.tmp` is cleaned by `open()`.

**Backup (`backup_to`)** copies the vault to `<dest>.tmp`, opens that copy under the
current master to prove it is a decryptable vault, then commits it to `dest`. It
refuses a destination that resolves to the live vault file.

**Legacy migration** (`paths._migrate`) uses the identical shape: fatal fsync of the
copy, atomic replace, best-effort post-commit cleanup, and it deletes the old vault
only after the new one is committed. If migration cannot complete, the legacy path
is used in place — the user is never shown an empty vault.

The `fsync` of the copy is **fatal** (never swallowed): a failed flush aborts before
the commit, leaving the original untouched. This flush is **platform-sensitive** —
how a descriptor must be opened for `fsync` differs across operating systems — so it
must be exercised on each supported OS, not merely mocked; see [§15](#15-testing) and
issue #38.

**Pre-commit vs. post-commit** is the central distinction and must never blur:

- *Before* `os.replace`: any failure leaves the previous vault openable under the
  current master and the session is restored (`VaultError`).
- *After* `os.replace`: the on-disk vault is the new one. A failure to reopen the
  session is reported as a **distinct** error (`VaultRotatedError` for rekey,
  `VaultRestoredError` for restore) — never an auth/"wrong password" error, never
  "unchanged." (Only `paths._migrate`, whose post-commit steps are pure cleanup,
  never flips its result after the commit.)

See invariants [4](#16-invariants-do-not-regress) and 5.

* * *

## 10. Secret lifecycle

Plaintext secrets are handled on a need-to-touch basis.

**Implemented (current behavior).**

- The master password is held only on the live `Vault` (in memory) while unlocked;
  `close()` drops it.
- The credential table lists **passwordless** `Credential` summaries —
  `list_credentials()` selects only `name` / `username` / timestamps, so ciphertext
  is never loaded merely to render the (masked) list
  ([invariant 7](#16-invariants-do-not-regress)).
- A password is fetched (`get_password`) only when the user copies or reveals one.
  A revealed cell is re-masked on lock.
- Copied passwords are auto-cleared after a fixed delay, and only if the clipboard
  still holds the value PetitePass placed there (so a value the user copied
  afterward is never wiped).
- Auto-lock (a fixed inactivity timeout) closes the vault, re-masks any revealed
  cells, and clears the clipboard.

**Design requirements.**

- Any future secret-bearing field (e.g. TOTP seeds, private notes) must follow the
  same rule: it is not loaded to render a list, only fetched when actually used, and
  it is subject to masking and auto-clear.
- Clipboard use is a convenience with a real security cost, and clearing the
  clipboard does **not** guarantee that a clipboard-history manager has not already
  captured the value. This limitation must be stated honestly, not papered over.

**Python memory limitations (honest non-guarantee).** Python cannot reliably
guarantee zeroization of immutable strings or of every intermediate copy the runtime
may make. The project minimizes secret lifetime and avoids unnecessary copies, but
it must **not** claim secure memory erasure it cannot deliver. Do not add bizarre
`ctypes`/buffer hacks whose only purpose is to *claim* zeroization; reducing lifetime
is the honest, maintainable mitigation. See
[invariant 12](#16-invariants-do-not-regress).

**Direction — hardening and "paranoid mode" (not yet implemented; issue #43).**
A single optional stricter configuration composed of *understandable knobs*, not a
second architecture and not hidden security magic. Candidate knobs:

- clipboard disabled, or a very short clipboard TTL;
- aggressive auto-lock;
- lock on OS session-lock;
- lock on suspend;
- temporary (auto-hiding) password reveal;
- best-effort "sensitive clipboard" hints where the platform supports them
  (so history managers skip the value);
- configurable timeout values;
- potentially an optional keyfile in the future.

Each knob must have simple, testable semantics. None of these OS-integration
behaviors is implemented today; the current auto-lock is an inactivity timer only.

* * *

## 11. Filesystem & storage

- Data directory: `platformdirs.user_data_dir("PetitePass", appauthor=False)` —
  `~/.local/share`, Application Support, or `%LOCALAPPDATA%`.
- Directory mode `0700`, vault-file mode `0600` (POSIX; no-ops on Windows).
- The vault filename is a fixed constant kept for backward compatibility.
- Writes that matter are atomic (temp + `fsync` + `os.replace`; see [§9](#9-vault-file-operations-and-durability)).

* * *

## 12. Schema evolution

**Implemented (current behavior).** The `Password` model has an implicit
`AutoField` integer primary key (`id`), but application operations address records
by `name`, which is declared `unique`. Two migration mechanisms exist: `paths._migrate`
moves a legacy `~/PetitePass` vault to the standard data directory (a file
replacement, so it uses the atomic protocol of [§9](#9-vault-file-operations-and-durability)),
and `Vault._migrate_schema` adds the unique-name index to older vaults on open (an
in-database change; if the vault already contains duplicate names the index cannot be
built and the application-level check in `add()` is relied on instead).

**Direction (issue #40).**

- Address records by a **stable id** rather than by display name, so entries can be
  renamed and can share a display name.
- Use an explicit schema-version mechanism such as SQLite's `PRAGMA user_version`,
  with **ordered, tested** migrations replacing the current one-off approach.

**Design requirement — do not conflate two kinds of migration.** An ordinary SQL
schema migration (adding a column or index, backfilling data) runs inside a normal
database **transaction**; it does *not* require copying and replacing the whole vault
file. The full copy / verify / `os.replace` protocol of [§9](#9-vault-file-operations-and-durability)
is required specifically when **replacing the authoritative vault file** (rekey,
restore, legacy relocation) or when a migration genuinely cannot be done in place and
must replace the file. Applying the heavyweight protocol to every routine migration
would add cost and failure modes for no benefit.

* * *

## 13. Supply-chain security

A password manager's own executable is inside the threat model: an attacker who can
alter what the user runs defeats every in-app protection. The goal is that a
skeptical user can independently verify which binary they are running.

**Implemented (current behavior).**

- Exact, pinned runtime dependency versions (`requirements.txt`).
- `pip-audit` runs in CI against the pinned requirements.
- Release builds publish a `SHA256SUMS.txt` alongside the artifacts.

**Direction (issue #46).**

- dependency **hashes** where practical (e.g. `--require-hashes`);
- GitHub Actions pinned to **immutable commit SHAs** rather than mutable tags;
- **artifact attestations / build provenance** (e.g. Sigstore-backed) tying each
  binary to this repository, commit, and workflow;
- an **SBOM** where practical;
- eventual **Windows Authenticode** signing;
- eventual **macOS Developer ID + notarization**;
- **reproducible builds** where feasible.

**Honest limitation.** A checksum file produced by the *same* workflow that produced
a malicious executable proves nothing on its own — both would be forged together.
`SHA256SUMS.txt` guards against accidental corruption and mirror tampering, not
against a compromised build pipeline. Independent provenance (attestations,
reproducible builds, external signing) is what raises the bar, which is why those are
the direction rather than more self-generated checksums.

* * *

## 14. Threat model

> **PetitePass protects a vault at rest. It does not make a compromised computer
> trustworthy.**

Once the vault is unlocked, its secrets exist in the process. A malicious process
running as the same user, an administrator, kernel-level malware, a keylogger, a
debugger, or any other compromised execution environment may be able to obtain those
secrets. **PetitePass must never claim to defeat this.** Stating the boundary
honestly is part of the design; auto-lock and short secret lifetimes *narrow* the
window but do not close it.

| # | Scenario                                         | Can PetitePass defend?                                                                                          |
| - | ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| A | Attacker steals the vault file                   | **Partially** — cost equals the master password against PBKDF2-HMAC-SHA512 × 256 000. Choose a strong master.   |
| B | Attacker steals vault + any auxiliary files      | **Yes** — there is no sidecar verifier; nothing cheaper than SQLCipher to attack.                              |
| C | Malicious process under the same user account    | **No** — once unlocked, secrets are in the session; no local manager can prevent this. Auto-lock narrows it.    |
| D | Untrusted / corrupt vault contents               | **Yes** — wrong-key, hollow, and non-vault files are refused at unlock; peewee parameterizes row SQL.           |
| E | Filesystem attacker (perms, races, replacement)  | **Mostly** — `0600`/`0700`, atomic writes. A user who can already write your files can still tamper.            |
| F | Supply chain                                     | **Reduced** — a curated ~5-package runtime, `pip-audit`, pinned versions, published checksums. See [§13](#13-supply-chain-security). |

What PetitePass fundamentally **cannot** do: protect decrypted secrets from other
code running as you (C). Everything else on this list is addressed by design, within
the honesty constraint above.

* * *

## 15. Testing

Security-relevant behavior is verified against **real SQLCipher**, never a mock —
the whole point is to exercise real encryption
([invariant 8](#16-invariants-do-not-regress)). The release binary additionally runs
a Qt-free `--selftest` (a real create → add → reopen → read round-trip) to prove the
native extension works in the frozen build.

**Design requirements and direction.**

- **Deterministic fault injection** around the durability boundaries — `shutil.copy2`,
  `fsync`, `os.replace`, and reconnect/reopen — asserting the property of
  [§9](#9-vault-file-operations-and-durability) holds after a failure at each point:
  one master opens one complete vault; a pre-commit failure leaves the old vault; a
  post-commit reopen failure surfaces as `VaultRotatedError` / `VaultRestoredError`;
  no successful operation loses entries.
- **Positive per-OS operation tests.** Each vault-replacing operation must be shown
  to *succeed* on a healthy filesystem on each supported OS — not only that failures
  abort cleanly. Platform-specific behavior must be exercised, not mocked. The
  Windows `fsync` bug (#38) is the cautionary example: a read-only-descriptor `fsync`
  succeeds on Linux but fails on Windows, and a Linux-only or mocked test cannot
  catch it.
- **State-machine / property testing** (issue #47) where it adds value, modelling
  sequences of operations over a real vault and checking the durability property
  across interleavings and injected failures.

* * *

## 16. Invariants (do not regress)

A change that violates any of these is a security regression, regardless of whether
tests pass:

1. **Authentication is decryption.** A session is valid **only** if the vault
   decrypts *and* the expected `password` table is present.
2. **Safe key path.** Key material reaches SQLCipher **only** through a reviewed,
   injection-safe keying path appropriate to the active vault format. Application
   code must never interpolate untrusted key material into ad-hoc SQL / `PRAGMA`
   strings. *(Current passphrases use peewee's escaping `passphrase=` / `rekey()`
   API; a future raw-key format would use SQLCipher's raw-key syntax through an
   equally reviewed path.)*
3. **No plaintext/malformed vault from bad input.** An empty or NUL master password
   is refused before any file is created or replaced, so it can never yield a
   plaintext or half-written vault.
4. **Single atomic commit.** Every vault-file replacement (rekey, restore, legacy
   relocation) works on a verified copy and commits with a **single** `os.replace`.
   The `fsync` of the copy is fatal (never swallowed). Before the commit, any failure
   leaves the previous vault openable under the current master.
5. **Distinct post-commit failures.** A failure to reopen the session **after** the
   `os.replace` commit is reported as a distinct error (`VaultRotatedError` for
   rekey, `VaultRestoredError` for restore), never as an auth/"wrong password" error
   and never as "unchanged."
6. **GUI never bypasses the Vault.** The GUI never accesses the ORM directly; all
   credential access goes through `VAULT.*`, and it catches `VaultError` (and
   subclasses) only.
7. **Listing loads no secrets.** The credential list never loads password ciphertext
   (or any future secret-bearing field) to render the table.
8. **Tested against real SQLCipher.** New security-relevant behavior ships with tests
   against real SQLCipher, including failure paths.
9. **Core operation never requires networking.** Storing and retrieving local
   secrets works with no network, account, or remote service. Introducing networking
   is a threat-model change, not a feature.
10. **No secondary authentication oracle.** No sidecar verifier or other secondary
    check may become authoritative for authentication.
11. **No silent data loss.** An operation reported as successful never silently loses
    committed entries.
12. **No dishonest guarantees.** Documentation and UI must not claim protections the
    implementation and runtime cannot actually provide (e.g. defeating a compromised
    host, or guaranteed memory zeroization in Python).
