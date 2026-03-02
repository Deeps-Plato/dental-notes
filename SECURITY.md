# Security Policy

## HIPAA Notice

This software is provided for development and evaluation purposes only.

**Before using with real patient data you MUST:**
1. Execute a Business Associate Agreement (BAA) with Anthropic at [console.anthropic.com](https://console.anthropic.com)
2. Complete a full HIPAA security risk assessment for your deployment environment
3. Implement appropriate access controls, workforce training, and incident response procedures
4. Ensure your network configuration (ngrok/Tailscale) complies with your organization's security policies

The authors make no warranties regarding HIPAA compliance for any specific deployment.

## Reporting a Vulnerability

If you discover a security vulnerability, please report it via GitHub Security Advisories
(Settings → Security → Advisories → New advisory) rather than a public issue.

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact (especially any PHI exposure risk)
- Suggested remediation if known

**Do not** include any real patient data in vulnerability reports.

## Security Controls

| Control | Implementation |
|---------|---------------|
| Encryption at rest | SQLCipher AES-256; key in platform keychain |
| Encryption in transit | HTTPS enforced (Dio rejects plain HTTP for non-localhost) |
| Authentication | `X-API-Key` on all backend endpoints; biometric/PIN app lock |
| PHI minimization | Backend receives no names/DOBs; audio deleted post-transcription |
| Audit logging | All DB mutations written to `audit_log` table |
| Timeout | 5-minute auto-lock on app |
