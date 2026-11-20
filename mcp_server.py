import json, sys
import audit as rakiza

TOOLS = [
    {
        "name": "audit_citations",
        "description": "Audit one or more OpenAlex Work IDs or DOIs against embedded Relate graphs (graph.rl and case.rl) for retraction footprints, structural reach, node-ablation chokepoints, and citation chains.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "identifiers": {"type": "array", "items": {"type": "string"}, "description": "List of OpenAlex Work IDs (e.g. W4224073284) or DOIs"},
                "add_live": {"type": "boolean", "default": False, "description": "Fetch missing papers from OpenAlex, link into graph.rl, and recompute dynamic deltas"}
            },
            "required": ["identifiers"]
        }
    },
    {
        "name": "simulate_node_removal",
        "description": "Simulate removing a paper from graph.rl to measure severed reachability paths, connected component shifts, and affected downstream studies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "OpenAlex Work ID or DOI to remove in simulation"}
            },
            "required": ["identifier"]
        }
    }
]

def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
    mid = msg.get("id")
    method = msg.get("method", "")
    if mid is None:
        continue
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "rakiza-mcp", "version": "1.0.0"}
        }})
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
    elif method == "tools/call":
        params = msg.get("params") or {}
        tname = params.get("name")
        targs = params.get("arguments") or {}
        try:
            if tname == "audit_citations":
                ids = targs.get("identifiers") or []
                live = bool(targs.get("add_live", False))
                res = [rakiza.audit(i, live) for i in ids]
                data = res[0] if len(res) == 1 else {"audited_count": len(res), "results": res}
            elif tname == "simulate_node_removal":
                data = rakiza.simulate_removal(targs.get("identifier", ""))
            else:
                send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Unknown tool: {tname}"}})
                continue
            send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps(data, indent=2, ensure_ascii=False)}]}})
        except Exception as e:
            send({"jsonrpc": "2.0", "id": mid, "result": {"isError": True, "content": [{"type": "text", "text": str(e)}]}})
    else:
        send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}})
