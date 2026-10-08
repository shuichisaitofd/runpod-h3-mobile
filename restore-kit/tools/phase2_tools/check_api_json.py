# Offline check of an API workflow against /object_info: node types, input names, link targets, combo values.
import json, sys, urllib.request

g = json.load(open(sys.argv[1]))
info = json.load(urllib.request.urlopen("http://127.0.0.1:8188/object_info"))
problems = []
for nid, node in g.items():
    spec = info.get(node["class_type"])
    if spec is None:
        problems.append(f"{nid}: unknown node {node['class_type']}")
        continue
    req, opt = spec["input"].get("required", {}), spec["input"].get("optional", {})
    known = dict(req, **opt)
    for name in req:
        if name not in node["inputs"] and not any(k.startswith(name + ".") for k in node["inputs"]):
            problems.append(f"{nid} {node['class_type']}: missing required '{name}'")
    for name, val in node["inputs"].items():
        base = name.split(".")[0]
        if base not in known:
            problems.append(f"{nid} {node['class_type']}: unknown input '{name}'")
            continue
        if isinstance(val, list):
            src = g.get(val[0])
            if src is None:
                problems.append(f"{nid}: '{name}' links to missing node {val[0]}")
            elif val[1] >= len(info[src["class_type"]]["output"]):
                problems.append(f"{nid}: '{name}' links to bad output {val}")
            continue
        t = known[base][0]
        opts = t if isinstance(t, list) else known[base][1].get("options") if t == "COMBO" else None
        if opts is not None and val not in opts:
            problems.append(f"{nid} {node['class_type']}: '{name}'='{val}' not available on this Pod")
print("\n".join(problems) if problems else "no problems")
