import re
from lxml import etree

def nstag(ns, tag):
    return "{%s}%s" % (ns, tag) if ns else tag

def line_ends(path):
    patterns = [
        re.compile(r"^M(-?\d+),(-?\d+)C-?\d+,-?\d+ -?\d+,-?\d+ (-?\d+),(-?\d+)$"),
        re.compile(r"^M(-?\d+),(-?\d+)L(-?\d+),(-?\d+)$"),
    ]
    
    for pat in patterns:
        match = pat.match(path)
        if match:
            return map(int, match.groups())
    
    return None

def import_svg(stream):
    ns = "http://www.w3.org/2000/svg"
    data = etree.parse(stream)
    nodes = {}
    edges = {}
    for group in data.iter(nstag(ns, "g")):
        cls = group.get("class")
        title = group.findtext(nstag(ns, "title"))
        if cls == "node":
            ellipse = group.find(nstag(ns, "ellipse"))
            x = int(ellipse.get("cx"))
            y = int(ellipse.get("cy"))
            sc = not "lightgrey" in ellipse.get("style")
            nodes[title] = x, y, sc
        elif cls == "edge":
            path = group.find(nstag(ns, "path"))
            edges[title] = line_ends(path.get("d"))
    return nodes, edges

def writeline(stream, line, *args):
    if args:
        line %= args
    print line
    newline = "\r\n"
    stream.write(line + newline)

def abbr(name):
    if len(name) == 2:
        return name[0] + name
    return name[:3]

def nodepoints(x, y, rx, ry):
    dx = rx * 3 // 4
    dy = ry * 3 // 4
    
    points = [
        (x - dx, y - dy),
        (x, y - ry),
        (x + dx, y - dy),
        (x + rx, y),
        (x + dx, y + dy),
        (x, y + ry),
        (x - dx, y + dy),
        (x - rx, y),
    ]
    
    return points

def export_map(nodes, edges, mapname):
    mapfile = open(mapname + ".map", "wb")
    aopfile = open(mapname + ".aop", "wb")
    left = right = top = bottom = None
    rx = 24
    ry = 18
    
    for name in sorted(nodes):
        x, y, sc = nodes[name]
        center = "SC" if sc else "NO"
        writeline(aopfile, "%s %s %s %s %s",
            x, y, abbr(name), center, name)
        
        if left is None or left > x:
            left = x
        if right is None or right < x:
            right = x
        if top is None or top > y:
            top = y
        if bottom is None or bottom < y:
            bottom = y
        
        points = nodepoints(x, y, rx, ry)
        writeline(mapfile, "%% %s", name)
        writeline(mapfile, "%s %s gm", *points[-1])
        for point in points:
            writeline(mapfile, "%s %s lin", *point)
        writeline(mapfile, "")
    
    for name in sorted(edges):
        x1, y1, x2, y2 = edges[name]
        writeline(mapfile, "%% %s", name)
        writeline(mapfile, "%s %s gm", x1, y1)
        writeline(mapfile, "%s %s lin", x2, y2)
        writeline(mapfile, "")
    
    inffile = open(mapname + ".inf", "wb")
    writeline(inffile, "Left:%d", left - 3*rx)
    writeline(inffile, "Top:%d", top - 3*ry)
    writeline(inffile, "Right:%d", right + 3*rx)
    writeline(inffile, "Bottom:%d", bottom + 3*ry)
    writeline(inffile, "Print:L")

def run(fname, mapname):
    nodes, edges = import_svg(open(fname))
    export_map(nodes, edges, mapname)

if __name__ == "__main__":
    run("doubstar.svg", "snark")
