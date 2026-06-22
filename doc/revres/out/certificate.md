# certificate — Architecture Brief

> Module: `certificate` · Category: Hidden/Tools · Depends: `base_setup` · `auto_install: false`
> Value model: **support** · Activity class: **support** · APQC: **8.0 Manage Information Technology**
> Odoo 19.0 · Facts: `doc/revres/facts/certificate.facts.json` · Frontend: `doc/revres/frontend/certificate.frontend.json`

## 1. Summary

`certificate` is **IT security / PKI infrastructure** — a server-side vault and crypto
utility for X.509 digital certificates and asymmetric private keys, used by document and
e-invoice signing. An admin uploads a certificate (DER, PEM or PKCS12) and, optionally, a
key; the module parses the bytes with the `cryptography` library, normalizes them to PEM,
extracts the subject / serial / validity window, and exposes a programmatic `_sign` API
that downstream localizations call to digitally sign documents. It owns **no business
object of its own**: 2 persistent models (`certificate.certificate`, `certificate.key`),
0 routes, restricted to `base.group_system`, `auto_install: false`, depending only on
`base_setup`. It is a pure technology-development utility consumed by other modules.

## 2. Structure (evidence)

- **Models:** `certificate.certificate` (the cert: `content`, `pkcs12_password`,
  `private_key_id`/`public_key_id`→`certificate.key`, computed-stored `pem_certificate`,
  `content_format`, `subject_common_name`, `serial_number`, `date_start`/`date_end`,
  `loading_error`, `is_valid`; `_order='date_end DESC'`); `certificate.key` (the key vault:
  `content`, `password`, computed-stored `pem_key`, `public`, `loading_error`). Both carry
  `company_id`→`res.company` (required, `ondelete=cascade`); 12 methods each.
- **Routes (0):** no web/RPC surface — all access is in-process ORM service methods.
- **Security:** 2 access rules (full CRUD to `base.group_system` only on both models),
  **2 record rules** (multi-company isolation: `company_id = False OR parent_of company_ids`),
  0 module groups.
- **Views:** 2 forms + 2 lists + 2 searches, plus a `res.config.settings` extension. Plain
  backend CRUD — no kanban/graph/pivot.

## 3. Frontend (gap #3) & Integrations (gap #7)

Frontend: **not present** — 0 JS files, 0 XML/OWL templates, 0 OWL components, 0 registry
adds, 0 patches, 0 services, no asset bundles. A pure server-side utility (static).
Integrations (gap #7): **0 outbound HTTP call sites**, `sdk_imports: ['requests']`,
`uses_api_keys: false`, no endpoints. The only flagged file is `tools/certificate_adapter.py`
— a `requests.adapters.HTTPAdapter` (`CertificateAdapter`) that, via pyOpenSSL + urllib3,
performs **mutual-TLS using in-memory `certificate.certificate`/`certificate.key` records**
instead of on-disk files. It is a transport helper, not an inbound surface.

## 4. Behavior (beyond metadata)

- **Cert parsing** (`certificate.certificate._compute_pem_certificate`, stored): decodes
  `content` and tries DER → PKCS12 (with `pkcs12_password`) → PEM via the `cryptography`
  library; on success stores `content_format`, normalized `pem_certificate`,
  `subject_common_name` (COMMON_NAME OID), `serial_number`, and the validity window
  `date_start`/`date_end` read from `not_valid_before/after` — with a `parse_version` guard
  switching to `not_valid_*_utc` on `cryptography>=42.0.0`. `is_valid` is a separate compute
  (`date_start<=now<=date_end` and no `loading_error`) with a matching `_search_is_valid`. (code-read)
- **PKCS12 self-extraction** (`_compute_private_key`): uploading a `.p12` bundle decodes the
  password-protected file, extracts the embedded private key, re-serializes it to unencrypted
  PKCS8 PEM and **creates (or de-dups) a `certificate.key` record**, linking `private_key_id`.
  An `@api.constrains` then re-loads both and uses `constant_time.bytes_eq` to assert the
  cert public key matches the linked key — `ValidationError` on mismatch. (code-read)
- **Key vault + crypto ops** (`certificate.key._compute_pem_key`, `_sign`, `_verify`,
  `_decrypt`): classifies uploaded bytes (private vs public) and stores normalized `pem_key`
  (private re-encrypted with `BestAvailableEncryption` when a password is set). `_sign` loads
  the PEM private key (decrypting with the stored password) and dispatches by type — EC→ECDSA,
  RSA→PKCS1v15, Ed25519→raw — over SHA1/SHA256; `_decrypt` handles RSA-OAEP. The model
  performs the actual cryptographic operations in-process. (code-read)
- **Signing entry point + key generation** (`certificate.certificate._sign`): the public
  signing path used by document/e-invoice callers — it guards on `is_valid` (UserError if
  expired/invalid) and on a present `private_key_id`, then delegates to `private_key_id._sign`.
  Byte getters (`_get_der_certificate_bytes`, `_get_fingerprint_bytes`, `_get_signature_bytes`,
  `_get_public_key_bytes`, `_get_public_key_numbers_bytes`) expose material for embedding in
  signed XML/PDF. `certificate.key` also ships `@api.model` generators
  `_generate_ec_private_key` (SECP256R1), `_generate_rsa_private_key` (exp 65537/3, ≥512-bit),
  `_generate_ed25519_private_key`. (code-read)
- **`cryptography`/pyOpenSSL dependency** (static + code-read): the whole module is a thin ORM
  wrapper over the Python `cryptography` package (`x509`, `hazmat.primitives`: serialization,
  hashes, asymmetric ec/rsa/ed25519/padding, `constant_time`, `pkcs12`), imported at module
  top level; `tools/certificate_adapter.py` adds pyOpenSSL/requests/urllib3. **None are
  declared in the manifest's `external_dependencies`** — they are de-facto hard deps. (code-read)

## 5. IT architecture

- **Application:** server-side X.509 certificate & private-key vault and signing/crypto utility.
- **Software services:** no routes; in-process methods `certificate.certificate._sign` + byte
  getters; `certificate.key._sign/_verify/_decrypt` + `_generate_ec/rsa/ed25519_private_key`;
  plus `tools.CertificateAdapter` (mutual-TLS HTTPAdapter from in-memory records).
- **Data objects:** `certificate.certificate`, `certificate.key`.
- **Information flows:** upload cert/key bytes → `cryptography` parse/validate → stored PEM +
  validity + linked key; PKCS12 upload → derived `certificate.key`; caller `._sign(message)` →
  validity/key guard → `key._sign` dispatch → signature bytes returned to the signing module;
  `CertificateAdapter` injects cert+key into pyOpenSSL/urllib3 for outbound mutual-TLS.

## 6. Business architecture

- **Capabilities (inferred):** store & normalize certificates (DER/PEM/PKCS12); manage key
  pairs; generate EC/RSA/Ed25519 keys; digitally sign (ECDSA/RSA/Ed25519, SHA1/SHA256);
  verify & RSA-OAEP decrypt; validate cert lifecycle (validity + cert/key compatibility);
  mutual-TLS transport from in-memory certs.
- **Value streams (inferred):** Upload-to-Usable-Credential (upload bytes → parse/validate →
  stored PEM + validity + linked key → ready to sign); Sign-on-Demand (`._sign` → validity/key
  guard → algorithm dispatch → signature returned to the document/e-invoice module).
- **Information concepts (auto):** `certificate.certificate` (digital certificate),
  `certificate.key` (cryptographic key / key pair).
- **Organization (auto):** `base.group_system` only — no module-specific groups. **Products (auto):** none.
- **Policies (inferred):** admin-only CRUD; multi-company `ir.rule` isolation; `@api.constrains`
  cert-must-load + cert/key public-material match (`constant_time`); `_sign` refuses
  invalid/expired certs or missing private key.
- **Metrics (inferred):** `is_valid` / `loading_error` as per-certificate health (no reports/KPIs shipped).
- **Strategy:** null (human). Confidence: concepts/org/products **auto**;
  capabilities/value_streams/policies/metrics **inferred**; strategy **human**.

## 7. Classification

- **Value model: support.** Firm IT/security (PKI) infrastructure — a credential vault plus
  signing/crypto primitives with no business object, document chain or transaction of its own.
  It holds no customer/order/product/ledger data; its only job is to store credentials and
  perform cryptographic operations that primary/support activities (e-invoicing, document
  signing, mutual-TLS) consume. Restricted to `base.group_system`, 0 routes, 0 reports →
  not chain/shop/network (Stabell & Fjeldstad "support").
- **APQC: 8.0 Manage Information Technology.** This is the "develop and manage IT security,
  privacy and data protection" capability expressed as running mechanism — cryptographic key
  management (generation, secure storage, certificate lifecycle) and digital signing. **11.0
  "Manage Enterprise Risk, Compliance, …"** was weighed (digital signatures serve e-invoice
  authenticity / non-repudiation, a compliance concern), but rejected: this module supplies
  only the technical cryptographic *mechanism*, not the governance, risk-assessment or audit
  *process* — that compliance use lives in the consuming localization modules. The dominant
  character is cryptographic key/certificate management infrastructure → squarely 8.0
  (mirrors the sibling `auth_passkey`/`auth_totp` IT-security records).

## 8. Fit-to-Standard

- **Standard:** upload & store X.509 in DER/PEM/PKCS12 with auto format detection; auto-extract
  subject/serial/validity; auto-derive & link the private key from a PKCS12 bundle; store and
  classify password-protected private/public keys per company; generate EC (SECP256R1)/RSA/
  Ed25519 key pairs; sign (ECDSA/RSA/Ed25519, SHA1/SHA256), verify, RSA-OAEP decrypt;
  cert/key compatibility + validity constraints; mutual-TLS transport from in-memory certs.
- **Typical fits:** credential store for country-specific e-invoicing/e-signature localizations
  reused unchanged; admin-only, multi-company certificate management out of the box; programmatic
  `_sign` API for any module needing X.509 signatures.
- **Common gaps:** no UI/workflow for expiry alerts or key rotation (only `is_valid`); limited
  algorithm coverage (EC fixed to SECP256R1; SHA1/SHA256 only); no HSM/external key-store
  integration (private keys stored in the DB); no enrollment/CA-issuance flow (import-only);
  manifest omits the `cryptography`/pyOpenSSL external dependencies.
- **Drive hints:** `env['certificate.key']._generate_rsa_private_key(env.company, name='demo_rsa')`;
  `k = env['certificate.key']._generate_ec_private_key(env.company); k._sign('hello')`;
  `env['certificate.certificate'].search_count([('is_valid','=',True)])`;
  `c = env['certificate.certificate'].browse(id); (c.subject_common_name, c.date_end, c.is_valid)`.

*Provenance: `extract_module.py` + `extract_frontend.py` + code-read of
`models/certificate.py`, `models/key.py`, and `tools/certificate_adapter.py`. Odoo 19.0.*
