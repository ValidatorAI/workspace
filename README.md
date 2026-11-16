# workspace — Hermes profile distribution

Generated 2026-11-16T15:58:01+03:30 from /home/siavash/.hermes/profiles/workspace by to-profile-dist.sh.

Install on any machine:
    hermes profile install <this-repo-git-url>
    cp ~/.hermes/profiles/workspace/.env.EXAMPLE ~/.hermes/profiles/workspace/.env   # fill keys, chmod 600
    hermes -p workspace chat -Q -q "reply with exactly: PROFILE-OK"

Iterate: edit the files here, bump version in distribution.yaml, push; then on each machine:
    hermes profile update workspace
User data (memories, sessions, .env, auth) is never overwritten by updates;
config.yaml is preserved unless --force-config.
