# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | Yes                |
| 0.1.x   | No                 |

## Reporting a Vulnerability

EasyQuant is a quantitative research framework intended for **backtesting and paper trading only**. It is not designed for handling real-money transactions or sensitive user data.

If you discover a security issue:

1. **Do not** open a public GitHub Issue.
2. Email the maintainer directly: `alanfok2868@gmail.com`
3. Include a description of the vulnerability, steps to reproduce, and suggested fix (if any).
4. We will respond within 48 hours and work with you to resolve the issue.

## Security Best Practices

- **Never** commit API keys, account IDs, or credentials to the repository
- Use `.env` or environment variables for sensitive configuration
- The `.gitignore` excludes `.env`, `.env.local`, and `*.local.json`
- Review strategy code before running with real accounts — EasyQuant provides no warranty for live trading losses
