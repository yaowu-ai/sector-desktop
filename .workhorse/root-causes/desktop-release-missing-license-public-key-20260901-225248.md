# Root Cause Report

## Machine Handoff

```json
{
  "schema_version": 1,
  "kind": "root-cause-report",
  "producer": "root-cause-analysis",
  "report_id": "desktop-release-missing-license-public-key-20260901-225248",
  "created_at": "2026-09-01T22:52:48+08:00",
  "status": "ROOT_CAUSE_LOCKED",
  "source_context": {
    "analysis_class": "non-trivial",
    "trivial_basis": null,
    "investigation_boundary": "Diagnose a Windows desktop login screen error that says the desktop client is missing License public key configuration after a remote-repository-built package is installed. Scope includes account-matrix remote-tracking Git trees, local ignored env files, release workflow, Vite build script, and desktop source code. Scope excludes GitHub repository secret configuration that is not readable from the repository.",
    "repository_root": "E:/YAOWU/yangHao/account-matrix",
    "code_revision": "account-matrix fd0502d369339be0c74f5c88c49758be55ecf1c8",
    "providers_used": [
      "user screenshot",
      "git remote-tracking tree",
      "repository source/config",
      "local ignored env file metadata"
    ]
  },
  "failure_object": {
    "trigger_input": "User runs a Windows desktop installer built from the remote account-matrix desktop release path and opens the login screen.",
    "state_environment": "Remote GitLab/GitHub feature/sector-desktop code at fd0502d; desktop production build mode; repository does not contain desktop/.env.production or desktop/.env.test; local workstation has those ignored files.",
    "failing_signal": "Login page displays '桌面端缺少 License 公钥配置'.",
    "expected_behavior": {
      "statement": "A production desktop package must include a non-empty VITE_LICENSE_PUBLIC_KEY value so the desktop client can verify the server-issued License signature.",
      "authority_evidence_ids": [
        "EV-006",
        "EV-007",
        "EV-008"
      ]
    },
    "actual_behavior": "The desktop client reports the License public key configuration is missing.",
    "affected_boundary": "account-matrix desktop frontend build-time environment injection for License verification",
    "nearby_objects_not_accepted": [
      "The prior unable-to-connect-to-server error is not accepted as the same failure object because this screenshot reports a different client-side configuration error.",
      "The presence of local ignored .env.production is not accepted as proof that remote release runners receive the same value.",
      "The presence of desktop/.env.example is not accepted as usable production configuration because it contains a placeholder key."
    ]
  },
  "evidence": [
    {
      "id": "EV-001",
      "kind": "user",
      "provider": "user-provided screenshot",
      "summary": "The screenshot shows the desktop login page with the error text '桌面端缺少 License 公钥配置'.",
      "source_anchor": {
        "type": "user-statement",
        "ref": "Conversation image attachment codex-clipboard-7e40730e-d665-4cf1-9359-6414235b0910.png"
      },
      "captured_at": "2026-09-01T22:40:00+08:00",
      "scope": "reported-instance",
      "same_failure_object": true,
      "same_causal_chain": true,
      "redacted": true,
      "proves": [
        "The current user-visible failure is the missing License public key configuration message."
      ],
      "does_not_prove": [
        "It does not prove which build system produced the installer or whether repository secrets exist outside the Git tree."
      ]
    },
    {
      "id": "EV-002",
      "kind": "runtime",
      "provider": "GitHub remote-tracking tree",
      "summary": "origin-github/feature/sector-desktop at fd0502d contains desktop/.env.example but not desktop/.env.production or desktop/.env.test.",
      "source_anchor": {
        "type": "command",
        "ref": "git ls-tree -r --name-only origin-github/feature/sector-desktop -- desktop; git show origin-github/feature/sector-desktop:desktop/.env.production returned path-not-in-tree"
      },
      "captured_at": "2026-09-01T22:45:00+08:00",
      "scope": "same-class",
      "same_failure_object": true,
      "same_causal_chain": true,
      "redacted": true,
      "proves": [
        "The GitHub remote branch does not carry the production/test env files needed by Vite file-based env loading."
      ],
      "does_not_prove": [
        "It does not prove whether GitHub Actions repository secrets are configured."
      ]
    },
    {
      "id": "EV-003",
      "kind": "runtime",
      "provider": "GitLab remote-tracking tree",
      "summary": "origin/feature/sector-desktop at fd0502d contains desktop/.env.example but not desktop/.env.production or desktop/.env.test. A live GitLab fetch timed out, but the remote-tracking ref was updated by the immediately preceding successful push.",
      "source_anchor": {
        "type": "command",
        "ref": "git rev-parse origin/feature/sector-desktop == fd0502d369339be0c74f5c88c49758be55ecf1c8; git ls-tree -r --name-only origin/feature/sector-desktop -- desktop"
      },
      "captured_at": "2026-09-01T22:45:00+08:00",
      "scope": "same-class",
      "same_failure_object": true,
      "same_causal_chain": true,
      "redacted": true,
      "proves": [
        "The GitLab remote-tracking branch does not carry production/test env files either."
      ],
      "does_not_prove": [
        "It does not prove GitLab CI variable configuration, and the live fetch timeout means it relies on the just-updated remote-tracking ref."
      ]
    },
    {
      "id": "EV-004",
      "kind": "source",
      "provider": "repository",
      "summary": ".gitignore ignores desktop/.env, desktop/.env.production, desktop/.env.test, desktop/.env.local, and desktop/.env.*.local while explicitly allowing desktop/.env.example.",
      "source_anchor": {
        "type": "file-line",
        "path": ".gitignore",
        "ref": ".gitignore:28-33",
        "content_sha256": "bfbd942e7bb52c68f62611f06b1b0964f10f5e58b4bb33d1b46e6b58bb21615b"
      },
      "captured_at": "2026-09-01T22:46:00+08:00",
      "scope": "same-class",
      "same_failure_object": true,
      "same_causal_chain": true,
      "redacted": true,
      "proves": [
        "The absence of production/test env files from the remote tree is intentional under current ignore rules."
      ],
      "does_not_prove": [
        "It does not prove whether an external CI secret could replace the files."
      ]
    },
    {
      "id": "EV-005",
      "kind": "config",
      "provider": "local ignored files",
      "summary": "Local desktop/.env.production and desktop/.env.test both contain VITE_DESKTOP_API_BASE_URL and a non-placeholder VITE_LICENSE_PUBLIC_KEY; desktop/.env.example contains a placeholder public key. Public key contents were not printed or persisted.",
      "source_anchor": {
        "type": "command",
        "ref": "PowerShell parsed desktop/.env.local, desktop/.env.test, desktop/.env.production, desktop/.env.example and emitted only presence, length, and placeholder status"
      },
      "captured_at": "2026-09-01T22:47:00+08:00",
      "scope": "supporting",
      "same_failure_object": true,
      "same_causal_chain": true,
      "redacted": true,
      "proves": [
        "The required production public key exists only in local ignored configuration, not in the committed remote tree."
      ],
      "does_not_prove": [
        "It does not prove the public key value is correct or that external CI secrets are absent."
      ]
    },
    {
      "id": "EV-006",
      "kind": "source",
      "provider": "repository",
      "summary": "desktop/.env.example documents VITE_DESKTOP_API_BASE_URL and VITE_LICENSE_PUBLIC_KEY; its public key value is a replacement placeholder.",
      "source_anchor": {
        "type": "file-line",
        "path": "desktop/.env.example",
        "ref": "desktop/.env.example:1-2",
        "content_sha256": "bbde4b70e5762e5fd1f7d2752c8c17919913eefc884846ff980543190d000170"
      },
      "captured_at": "2026-09-01T22:45:00+08:00",
      "scope": "supporting",
      "same_failure_object": true,
      "same_causal_chain": true,
      "redacted": true,
      "proves": [
        "The repository declares that a License public key env var is required for desktop builds."
      ],
      "does_not_prove": [
        "It does not provide a production-usable public key."
      ]
    },
    {
      "id": "EV-007",
      "kind": "project-docs",
      "provider": "repository",
      "summary": "desktop/docs/desktop-api-base-url.md states that VITE_LICENSE_PUBLIC_KEY is an Ed25519 PEM public key used to verify the server-returned signedPayload and signature.",
      "source_anchor": {
        "type": "file-line",
        "path": "desktop/docs/desktop-api-base-url.md",
        "ref": "desktop/docs/desktop-api-base-url.md:21",
        "content_sha256": "964fc138da98565bc3d99220b235280682e1301049c8fc25878048eaf77a90d6"
      },
      "captured_at": "2026-09-01T22:48:00+08:00",
      "scope": "supporting",
      "same_failure_object": true,
      "same_causal_chain": true,
      "redacted": true,
      "proves": [
        "The product contract expects VITE_LICENSE_PUBLIC_KEY to be present in desktop builds."
      ],
      "does_not_prove": [
        "It does not prove which build injected or omitted the variable."
      ]
    },
    {
      "id": "EV-008",
      "kind": "source",
      "provider": "repository",
      "summary": "desktop/src/vite-env.d.ts declares VITE_LICENSE_PUBLIC_KEY as a Vite-exposed optional env var.",
      "source_anchor": {
        "type": "file-line",
        "path": "desktop/src/vite-env.d.ts",
        "ref": "desktop/src/vite-env.d.ts:3-6",
        "content_sha256": "b09a2834f1268dda373dae26acf886ab80ebdde8c798e8197af768cfae7e4858"
      },
      "captured_at": "2026-09-01T22:49:00+08:00",
      "scope": "same-class",
      "same_failure_object": true,
      "same_causal_chain": true,
      "redacted": true,
      "proves": [
        "Only a VITE-prefixed env value is intended to reach the desktop frontend bundle."
      ],
      "does_not_prove": [
        "It does not prove the env var was present during any specific build."
      ]
    },
    {
      "id": "EV-009",
      "kind": "source",
      "provider": "repository",
      "summary": "desktop/scripts/build.mjs invokes Vite with --mode production when the build mode is production.",
      "source_anchor": {
        "type": "file-line",
        "path": "desktop/scripts/build.mjs",
        "ref": "desktop/scripts/build.mjs:3-7",
        "content_sha256": "97fa9b8cbfbf3675984a1091823f51429de7c1f42d892ffede41fecb4d70b871"
      },
      "captured_at": "2026-09-01T22:49:00+08:00",
      "scope": "same-class",
      "same_failure_object": true,
      "same_causal_chain": true,
      "redacted": true,
      "proves": [
        "Production package builds rely on Vite production-mode env resolution plus process environment."
      ],
      "does_not_prove": [
        "It does not prove process.env contained or omitted the public key in CI."
      ]
    },
    {
      "id": "EV-010",
      "kind": "source",
      "provider": "repository",
      "summary": "The GitHub release workflow checks out the repository and runs desktop-build.ps1 with BuildMode production, but the workflow file contains no VITE_LICENSE_PUBLIC_KEY or VITE_DESKTOP_API_BASE_URL env injection in the Windows or macOS build steps.",
      "source_anchor": {
        "type": "file-line",
        "path": ".github/workflows/release-desktop.yml",
        "ref": ".github/workflows/release-desktop.yml:72-74,108-112,144-148",
        "content_sha256": "12a537beff95a1662204e11f4eae39df0fac9ee01744bbb3a91f5fa3df093b91"
      },
      "captured_at": "2026-09-01T22:50:00+08:00",
      "scope": "same-class",
      "same_failure_object": true,
      "same_causal_chain": true,
      "redacted": true,
      "proves": [
        "The checked-in GitHub release workflow does not inject the public key from secrets into the build process."
      ],
      "does_not_prove": [
        "It does not prove an unobserved manual local build lacked the variable, nor can it inspect GitHub secret storage."
      ]
    },
    {
      "id": "EV-011",
      "kind": "source",
      "provider": "repository",
      "summary": "desktopApi.ts sets DEFAULT_LICENSE_PUBLIC_KEY from import.meta.env.VITE_LICENSE_PUBLIC_KEY or an empty string; hasLicensePublicKey checks for non-empty value; License verification throws '桌面端缺少 License 公钥配置' when missing.",
      "source_anchor": {
        "type": "file-line",
        "path": "desktop/src/services/desktopApi.ts",
        "ref": "desktop/src/services/desktopApi.ts:12,169-174,357-358",
        "content_sha256": "589da5dcebc8cbab1b08386df5ab66d8b2301963cf63b6a4be2b24e9495502c0"
      },
      "captured_at": "2026-09-01T22:49:00+08:00",
      "scope": "same-class",
      "same_failure_object": true,
      "same_causal_chain": true,
      "redacted": true,
      "proves": [
        "A build with no VITE_LICENSE_PUBLIC_KEY produces the exact observed error path."
      ],
      "does_not_prove": [
        "It does not prove whether the missing env came from remote CI, local packaging, or another release process without build identity."
      ]
    }
  ],
  "claims": [
    {
      "id": "CL-001",
      "status": "observed",
      "statement": "The current failure object is the desktop login page reporting missing License public key configuration.",
      "evidence_ids": [
        "EV-001"
      ],
      "does_not_prove": [
        "It does not identify the build system by itself."
      ],
      "consumers": [
        "release triage",
        "$code-bugfix"
      ]
    },
    {
      "id": "CL-002",
      "status": "observed",
      "statement": "The remote feature/sector-desktop Git trees contain only desktop/.env.example and do not contain desktop/.env.production or desktop/.env.test.",
      "evidence_ids": [
        "EV-002",
        "EV-003",
        "EV-004"
      ],
      "does_not_prove": [
        "It does not rule out external CI secrets."
      ],
      "consumers": [
        "release triage",
        "$code-bugfix"
      ]
    },
    {
      "id": "CL-003",
      "status": "observed",
      "statement": "The required production License public key exists in local ignored env files but not in the committed remote tree.",
      "evidence_ids": [
        "EV-005",
        "EV-006"
      ],
      "does_not_prove": [
        "It does not prove the public key value is valid."
      ],
      "consumers": [
        "release triage",
        "$code-bugfix"
      ]
    },
    {
      "id": "CL-004",
      "status": "observed",
      "statement": "The checked-in GitHub desktop release workflow does not inject VITE_LICENSE_PUBLIC_KEY into Windows or macOS production build steps.",
      "evidence_ids": [
        "EV-009",
        "EV-010"
      ],
      "does_not_prove": [
        "It does not prove an unrelated manual build process lacked the variable."
      ],
      "consumers": [
        "release triage",
        "$code-bugfix"
      ]
    },
    {
      "id": "CL-005",
      "status": "root-cause",
      "statement": "Remote-repository production desktop builds have no committed production env file and the checked-in release workflow does not inject VITE_LICENSE_PUBLIC_KEY, so the built frontend receives an empty License public key and the desktop client raises the observed missing-public-key error.",
      "evidence_ids": [
        "EV-001",
        "EV-002",
        "EV-004",
        "EV-005",
        "EV-009",
        "EV-010",
        "EV-011"
      ],
      "does_not_prove": [
        "It does not prove GitHub/GitLab secret stores are empty; it proves the checked-in remote code and workflow do not provide the variable to the release build."
      ],
      "consumers": [
        "$code-bugfix",
        "release pipeline fix",
        "desktop package verification"
      ]
    }
  ],
  "hypotheses": [
    {
      "id": "H-001",
      "status": "root-cause",
      "statement": "The installer was built from remote code without VITE_LICENSE_PUBLIC_KEY being available to Vite, because production/test env files are ignored and absent from the remote tree and the checked-in release workflow does not inject the variable.",
      "evidence_for_ids": [
        "EV-001",
        "EV-002",
        "EV-004",
        "EV-005",
        "EV-009",
        "EV-010",
        "EV-011"
      ],
      "evidence_against_ids": [],
      "challenge": "Check remote Git trees, ignore rules, workflow env injection, local ignored env presence, and the exact code branch that throws the screenshot error.",
      "would_disprove": "A matching release build log or artifact proof showing VITE_LICENSE_PUBLIC_KEY was injected and non-empty for the failing installer would disprove this hypothesis."
    },
    {
      "id": "H-002",
      "status": "ruled-out",
      "statement": "The error is caused only by the production API base URL being wrong.",
      "evidence_for_ids": [],
      "evidence_against_ids": [
        "EV-001",
        "EV-011"
      ],
      "challenge": "Compare the screenshot text with the client branches for API URL errors versus License public key errors.",
      "would_disprove": "A source path mapping an API URL failure to the exact missing-License-public-key message would reopen this hypothesis."
    },
    {
      "id": "H-003",
      "status": "ruled-out",
      "statement": "The committed desktop/.env.example supplies a usable License public key to production builds.",
      "evidence_for_ids": [],
      "evidence_against_ids": [
        "EV-006"
      ],
      "challenge": "Inspect desktop/.env.example content and placeholder status.",
      "would_disprove": "A committed .env.example with the real production public key and a build process that copies it to .env.production would reopen this hypothesis."
    }
  ],
  "causal_chain": {
    "first_wrong_step": "EDGE-001",
    "first_wrong_step_edge_id": "EDGE-001",
    "edges": [
      {
        "id": "EDGE-001",
        "from": "remote release build input",
        "to": "production build environment lacks VITE_LICENSE_PUBLIC_KEY",
        "relation": "The remote branch omits ignored production/test env files and the checked-in release workflow does not inject the variable.",
        "evidence_ids": [
          "EV-002",
          "EV-004",
          "EV-005",
          "EV-009",
          "EV-010"
        ]
      },
      {
        "id": "EDGE-002",
        "from": "production build environment lacks VITE_LICENSE_PUBLIC_KEY",
        "to": "built frontend embeds DEFAULT_LICENSE_PUBLIC_KEY as an empty string",
        "relation": "desktopApi.ts reads import.meta.env.VITE_LICENSE_PUBLIC_KEY and falls back to ''.",
        "evidence_ids": [
          "EV-008",
          "EV-011"
        ]
      },
      {
        "id": "EDGE-003",
        "from": "built frontend embeds DEFAULT_LICENSE_PUBLIC_KEY as an empty string",
        "to": "License verification reports missing public key on the login screen",
        "relation": "hasLicensePublicKey returns false and desktopApi.ts throws the exact observed message.",
        "evidence_ids": [
          "EV-001",
          "EV-011"
        ]
      }
    ]
  },
  "contradictions": [],
  "open_unknowns": [
    {
      "id": "U-001",
      "question": "Are GitHub or GitLab repository secret stores configured with VITE_LICENSE_PUBLIC_KEY?",
      "impact": "scope-only",
      "owner": "repository administrator",
      "next_step": "If the release workflow is changed to reference secrets, verify the secret exists and is non-empty in each platform."
    }
  ],
  "repair_handoff": {
    "readiness": "READY_FOR_DECISION",
    "consumer": "$code-bugfix",
    "root_cause_claim_id": "CL-005",
    "repair_boundary": "Release configuration and build-time env validation for account-matrix desktop. Either inject VITE_LICENSE_PUBLIC_KEY via CI secrets/workflow env for all desktop build jobs, or provide a committed non-secret public-key source used by production builds; add a build/test guard that fails when the production public key is absent or placeholder.",
    "regression_observable": "A production desktop build without a usable VITE_LICENSE_PUBLIC_KEY must fail before packaging, and a correctly configured build must not show '桌面端缺少 License 公钥配置' on login.",
    "constraints": [
      "Do not commit private signing keys or secrets.",
      "The License verification public key is public by design, but its distribution policy should be decided explicitly before committing it.",
      "Keep API base URL and License public key checks independent so one missing variable cannot hide the other."
    ],
    "risk_decisions": [
      {
        "id": "D-001",
        "question": "Should the production License public key be committed as a public constant/env template value, or injected from CI secrets?",
        "status": "OPEN",
        "reason": "The key is a public verification key, but the team may still prefer release-time secret management for operational consistency.",
        "resolution": null
      }
    ]
  }
}
```

## Diagnosis Summary

Terminal: `ROOT_CAUSE_LOCKED`.

The screenshot error is caused by a production desktop build that does not receive `VITE_LICENSE_PUBLIC_KEY`. The remote `feature/sector-desktop` code contains only `desktop/.env.example`; `.env.production`, `.env.test`, and `.env.local` are ignored and absent from the remote Git trees. The checked-in GitHub release workflow runs production desktop builds but does not inject `VITE_LICENSE_PUBLIC_KEY`. In that state, `desktopApi.ts` falls back to an empty public key and throws the exact message shown in the screenshot.

## Source Context

Repository root: `E:/YAOWU/yangHao/account-matrix`.

Revision inspected: `fd0502d369339be0c74f5c88c49758be55ecf1c8`.

Evidence providers: user screenshot, GitHub/GitLab remote-tracking trees, repository source/config, and redacted metadata from local ignored env files. GitHub fetch succeeded. GitLab live fetch timed out, but the inspected GitLab remote-tracking ref was updated by the immediately preceding successful push.

## Failure Object

Trigger: a user opens a Windows desktop installer built from the remote desktop release path.

Expected: production desktop builds contain a non-empty License verification public key.

Actual: the login screen reports missing License public key configuration.

Affected boundary: `account-matrix` desktop frontend build-time environment injection for License verification.

## Evidence Ledger

| ID | Kind / provider | Minimal redacted observation | Source anchor | Proves | Does not prove |
| --- | --- | --- | --- | --- | --- |
| EV-001 | user / screenshot | Login page shows `桌面端缺少 License 公钥配置`. | Conversation image attachment | The current failure signal. | Build identity or secret-store state. |
| EV-002 | git-tree / GitHub | GitHub remote tree has `desktop/.env.example`; no `desktop/.env.production` or `.env.test`. | `git ls-tree` / `git show`, `fd0502d` | Production/test env files are absent from remote code. | External CI secrets. |
| EV-003 | git-tree / GitLab | GitLab remote-tracking tree has same env-file absence at `fd0502d`. | `git rev-parse`, `git ls-tree` | GitLab-tracked branch has the same committed files. | Live GitLab state after fetch timeout. |
| EV-004 | source / `.gitignore` | `desktop/.env.production`, `.env.test`, `.env.local` are ignored; `.env.example` is allowed. | `.gitignore:28-33`, SHA-256 `BFBD942E7BB52C68F62611F06B1B0964F10F5E58B4BB33D1B46E6B58BB21615B` | Env-file absence is explained by ignore rules. | CI secrets. |
| EV-005 | local config metadata | Local ignored `.env.production` and `.env.test` contain non-placeholder public-key values; `.env.example` is placeholder. | Redacted PowerShell parse | Required value exists locally but is not committed. | Key correctness. |
| EV-006 | source / `.env.example` | Example documents `VITE_LICENSE_PUBLIC_KEY` but uses replacement placeholder. | `desktop/.env.example:1-2`, SHA-256 `BBDE4B70E5762E5FD1F7D2752C8C17919913EEFC884846FF980543190D000170` | Example is not production usable. | Production key value. |
| EV-007 | docs / repository | Docs say `VITE_LICENSE_PUBLIC_KEY` is the Ed25519 PEM public key for License verification. | `desktop/docs/desktop-api-base-url.md:21` | Product expectation for key presence. | Build injection. |
| EV-008 | source / Vite env typing | `VITE_LICENSE_PUBLIC_KEY` is a Vite-exposed optional env var. | `desktop/src/vite-env.d.ts:3-6`, SHA-256 `B09A2834F1268DDA373DAE26ACF886AB80EBDDE8C798E8197AF768CFAE7E4858` | Frontend needs a `VITE_` variable. | Runtime value. |
| EV-009 | source / build script | Build script runs `vite build --mode production`. | `desktop/scripts/build.mjs:3-7`, SHA-256 `97FA9B8CBFBF3675984A1091823F51429DE7C1F42D892FFEDE41FECB4D70B871` | Production build relies on Vite env resolution/process env. | CI process env contents. |
| EV-010 | source / release workflow | Workflow builds Windows/macOS production packages without `VITE_LICENSE_PUBLIC_KEY` env injection. | `.github/workflows/release-desktop.yml:72-74,108-112,144-148`, SHA-256 `12A537BEFF95A1662204E11F4EAE39DF0FAC9EE01744BBB3A91F5FA3DF093B91` | Checked-in release workflow does not provide the variable. | Secret store absence. |
| EV-011 | source / desktop API client | Missing `VITE_LICENSE_PUBLIC_KEY` falls back to `''`; verification throws exact screenshot error. | `desktop/src/services/desktopApi.ts:12,169-174,357-358`, SHA-256 `589DA5DCEBC8CBAB1B08386DF5AB66D8B2301963CF63B6A4BE2B24E9495502C0` | Missing env produces the observed message. | Which release process omitted it. |

## Claims

| ID | Status | Claim | Evidence | Does not prove | Consumers |
| --- | --- | --- | --- | --- | --- |
| CL-001 | observed | The current UI failure is missing License public key configuration. | EV-001 | Build identity. | release triage, `$code-bugfix` |
| CL-002 | observed | Remote branch does not contain production/test env files. | EV-002, EV-003, EV-004 | External secrets. | release triage, `$code-bugfix` |
| CL-003 | observed | Local ignored env files contain the needed value; committed example is placeholder. | EV-005, EV-006 | Key correctness. | release triage |
| CL-004 | observed | Checked-in release workflow does not inject `VITE_LICENSE_PUBLIC_KEY`. | EV-009, EV-010 | Unrelated manual build processes. | release triage |
| CL-005 | root-cause | Remote-repository production desktop builds have no committed production env file and no workflow injection for `VITE_LICENSE_PUBLIC_KEY`, causing an empty embedded public key and the observed error. | EV-001, EV-002, EV-004, EV-005, EV-009, EV-010, EV-011 | Secret-store state outside code. | `$code-bugfix`, release pipeline fix |

## Hypotheses

| ID | Status | Hypothesis | Evidence for / against | Challenge |
| --- | --- | --- | --- | --- |
| H-001 | root-cause | The installer was built without `VITE_LICENSE_PUBLIC_KEY` available to Vite. | For: EV-001, EV-002, EV-004, EV-005, EV-009, EV-010, EV-011 | Disprove with a matching failing build log proving the variable was injected and non-empty. |
| H-002 | ruled-out | The screenshot is caused only by wrong API base URL. | Against: EV-001, EV-011 | Reopen only if API URL failure maps to the exact missing-key message. |
| H-003 | ruled-out | `.env.example` supplies a usable production public key. | Against: EV-006 | Reopen only if committed example or a copy step provides a real key. |

## Causal Chain

`remote release build input` -> `production build environment lacks VITE_LICENSE_PUBLIC_KEY` -> `built frontend embeds empty DEFAULT_LICENSE_PUBLIC_KEY` -> `License verification throws "桌面端缺少 License 公钥配置"`.

First wrong step: `EDGE-001`, the release build input does not provide `VITE_LICENSE_PUBLIC_KEY`.

## Contradictions

None observed.

## Open Unknowns

U-001: Whether GitHub/GitLab secret stores already contain a public key. This is scope-only because the checked-in workflow does not reference those secrets today.

## Repair Handoff

Ready for decision. Fix the release/build boundary by either injecting `VITE_LICENSE_PUBLIC_KEY` from CI secrets into every desktop build job, or committing the public verification key through an explicit non-secret production config path. Add a build guard so production packaging fails if the key is missing or still a placeholder.
