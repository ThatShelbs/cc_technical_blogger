# Security policy

## Reporting a vulnerability

Please report security issues privately using GitHub's **Report a vulnerability** button on the repository's Security tab, rather than opening a public issue. Include steps to reproduce and the impact you see. You can expect an acknowledgement within a week.

## How Proseferno handles sensitive data

- **Local by design.** The app binds to `127.0.0.1` and stores all content under `data/` on your machine.
- **Secrets** (Anthropic API key, Cloudflare token) are stored in the operating system keychain through the `keyring` library. They are never written to the database, logs, exports or the repository. *Sign in with Claude* credentials are managed by the Anthropic CLI in its own config folder.
- **Model output is untrusted.** Model-authored SVG is parsed with external entities and network access disabled, then stripped of scripts, event handlers, `foreignObject` and external references before it is rasterized. Charts are declarative Vega-Lite specs and must carry inline data (no URLs). No model-generated code is executed.
- **Uploads** are size-limited, file names are sanitized, and files are parsed, never executed.
- **Network access** goes only to the services you configure: the Claude API, Cloudflare Workers AI, and URLs you ask Proseferno to import.

## Supported versions

Security fixes are made on the latest release.
