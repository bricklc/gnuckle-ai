# Security

Security reports should be sent privately to the project maintainer through the contact channel listed on the repository profile or by opening a private security advisory on GitHub if available. Do not open public issues for suspected vulnerabilities.

## Disclosure Posture

Gnuckle validates benchmark-pack manifests, verifies dataset integrity with SHA256, records audit events, and sanitizes the subprocess environment used for pack execution. These checks reduce risk, but they do not make gnuckle a sandbox.

## Installation Warnings

> **Benchmark packs are community-submitted content.** The gnuckle core team reviews contributions to the benchmark-index repository, but review is best-effort and cannot guarantee absence of bugs, vulnerabilities, or malicious behavior. Installation of third-party benchmark packs is at your own risk.
>
> **Gnuckle is not a sandbox.** Running gnuckle, with or without benchmark packs, executes local binaries with your user's privileges. Do not run gnuckle as root, administrator, or inside a production environment. Prefer a dedicated user or container.
>
> **Datasets are downloaded from third-party sources.** We verify SHA256 checksums, but dataset content should still be treated as untrusted input.
>
> **Code-plugin benchmarks execute arbitrary Python.** Do not install a code-plugin pack unless you trust the author and have read the plugin source.
>
> **No warranty.** Gnuckle is provided "as is" without warranty of any kind.
