#!/usr/bin/env python3
"""Call a PWR MCP tool over raw JSON-RPC. Usage: pwr_mcp.py <scope> <tool> ['<json-args>']
scope: mcp | action | read | knowledge | task | config
Reads MCP_AUTH_TOKEN from the PWR repo .env (dotenv; NOT in the server process env).
Response payload lives as a JSON string in result.content[0].text — parse twice."""
import json, re, sys, urllib.request

ENVFILE = "/home/siavash/Documents/codes/Pavel/W/pwr/.env"

def token():
    for line in open(ENVFILE):
        m = re.match(r'^MCP_AUTH_TOKEN=(.*)$', line.strip())
        if m:
            return m.group(1).strip().strip('"').strip("'")
    raise SystemExit("MCP_AUTH_TOKEN not found in " + ENVFILE)

def call(scope, tool, args):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": args}}).encode()
    req = urllib.request.Request(f"http://localhost:3000/{scope}-mcp", data=body,
                                 headers={"Authorization": "Bearer " + token(),
                                          "Content-Type": "application/json"})
    print(urllib.request.urlopen(req, timeout=60).read().decode())

if __name__ == "__main__":
    scope, tool = sys.argv[1], sys.argv[2]
    a = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    call(scope, tool, a)
