r'''Parlance variant migrator
    Copyright (C) 2004-2008  Eric Wald
    
    This module harfs variant files as distributed with David's server,
    creating configuration files readable by Parlance software.
    
    Parlance may be used, modified, and/or redistributed under the terms of
    the Artistic License 2.0, as published by the Perl Foundation.
'''#'''

import re
from itertools import chain
from operator import itemgetter
from os import path
from shlex import shlex
from parlance.functions import defaultdict

def lex(stream):
    # shlex doesn't handle strings well, but is fine for our purposes.
    for token in shlex(stream):
        yield token.upper()

def parse_file(filename, parser):
    result = None
    try:
        stream = open(filename, 'rU', 1)
    except IOError, err:
        raise IOError("Failed to open file %r %s" % (filename, err.args))
    
    try: result = parser(stream)
    finally: stream.close()
    return result

def parse_variants(stream):
    name_pattern = re.compile('<td>(\w[^<]*)</td><td>(\w+)</td>')
    file_pattern = re.compile("<a href='([^']+)'>(\w+)</a>")
    descrip = name = None
    for line in stream:
        match = name_pattern.search(line)
        if match:
            descrip, name = match.groups()
            files = {}
        elif name and descrip:
            match = file_pattern.search(line)
            if match:
                ref, ext = match.groups()
                files[ext.lower()] = path.normpath(ref)
            elif '</tr>' in line:
                run_variant(name, descrip, files)
                descrip = name = None

def parse_names(stream):
    powers = {}
    provinces = {}
    for line in stream:
        fields = line.strip().split(':')
        if len(fields) == 2:
            provinces[fields[0].upper()] = fields[1]
        elif len(fields) == 3:
            powers[fields[0].upper()] = (fields[1], fields[2])
    return powers, provinces

def parse_centers(stream):
    tokens = lex(stream)
    assert tokens.next() == "SCO"
    ownership = {}
    for token in tokens:
        assert token == "("
        power = tokens.next()
        ownership[power] = centers = set()
        for province in tokens:
            if province == ")":
                break
            else:
                centers.add(province)
    return ownership

def parse_position(stream):
    tokens = lex(stream)
    assert tokens.next() == "NOW"
    
    season = []
    assert tokens.next() == "("
    for token in tokens:
        if token == ")":
            break
        else:
            season.append(token)
    
    position = defaultdict(set)
    for token in tokens:
        if token == ")":
            # Left over from a coastline specification
            continue
        assert token == "("
        power = tokens.next()
        unit = []
        for item in tokens:
            if item == ")":
                break
            elif item != "(":
                unit.append(item)
        
        position[power].add(tuple(unit))
    return season, position

def parse_definition(stream):
    tokens = lex(stream)
    assert tokens.next() == "MDF"
    
    homes = {"UNO": set()}
    assert tokens.next() == "("
    for token in tokens:
        if token == ")":
            break
        else:
            homes[token] = set()
    
    borders = {}
    assert tokens.next() == "("
    assert tokens.next() == "("
    for token in tokens:
        if token == ")":
            break
        assert token == "("
        power = tokens.next()
        if power == "(":
            powers = []
            for power in tokens:
                if power == ")":
                    break
                else:
                    powers.append(power)
        else:
            powers = [power]
        
        for province in tokens:
            if province == ")":
                break
            else:
                borders[province] = {}
                for power in powers:
                    homes[power].add(province)
    
    assert tokens.next() == "("
    for token in tokens:
        if token == ")":
            break
        else:
            borders[token] = {}
    
    assert tokens.next() == ")"
    assert tokens.next() == "("
    for token in tokens:
        if token == ")":
            break
        assert token == "("
        province = tokens.next()
        sites = borders[province]
        for item in tokens:
            if item == ")":
                break
            assert item == "("
            unittype = tokens.next()
            if unittype == "(":
                unittype = tokens.next() + " " + tokens.next()
                assert tokens.next() == ")"
            sites[unittype] = site = set()
            for prov in tokens:
                if prov == ")":
                    break
                elif prov == "(":
                    prov = tokens.next() + " " + tokens.next()
                    assert tokens.next() == ")"
                site.add(prov)
    return homes, borders

def parse_files(name, description, mdf, sco, now, nam=None):
    groups = []
    season, position = parse_position(open(now))
    groups.append(spit_variant(name, season, description))
    groups.append(spit_positions(position))
    
    # Todo: Skip this part if ownership can be derived from position
    ownership = parse_centers(open(sco))
    groups.append(spit_centers("ownership", ownership))
    
    # Todo: Skip this part if another variant can be re-used
    homes, borders = parse_definition(open(mdf))
    groups.append(spit_centers("homes", homes))
    groups.append(spit_borders(borders))
    
    if nam:
        powers, provinces = parse_names(open(nam))
        groups.append(spit_powers(powers))
        groups.append(spit_provinces(provinces))
    
    return chain(*groups)

def spit_variant(name, season, description=None):
    yield "[variant]"
    yield "name=" + name
    yield "judge=standard"
    if description:
        yield "description=" + description
    yield "start=" + str.join(" ", season)
    yield ""

def spit_powers(powers):
    yield "[powers]"
    for key in sorted(powers):
        yield key + "=" + str.join(",", powers[key])
    yield ""

def spit_provinces(provinces):
    yield "[provinces]"
    for key in sorted(provinces):
        yield key + "=" + provinces[key]
    yield ""

def spit_centers(group, centers):
    yield "[" + group + "]"
    neutral = None
    for key in sorted(centers):
        line = key + "=" + str.join(",", sorted(centers[key]))
        if key == "UNO":
            neutral = line
        else:
            yield line
    if neutral:
        yield neutral
    yield ""

def spit_positions(positions):
    yield "[positions]"
    for key in sorted(positions):
        units = sorted(positions[key], key=itemgetter(1))
        value = ",".join(str.join(" ", unit) for unit in units)
        yield key + "=" + value
    yield ""

def spit_borders(borders):
    yield "[borders]"
    def wrap(s):
        if " " in s:
            return "(" + s + ")"
        else:
            return s
    
    for province in sorted(borders):
        sites = borders[province]
        items = []
        for key in sorted(sites):
            bits = chain([key], sorted(sites[key]))
            items.append(" ".join(wrap(bit) for bit in bits))
        yield province + "=" + str.join(", ", items)
    yield ""

def write_file(basename, stream):
    output = open(basename + ".cfg", "w")
    output.writelines(line + "\n" for line in stream)
    output.close()

def run_variant(name, description, files):
    print name + ": " + description
    lines = parse_files(name, description, files["mdf"],
        files["sco"], files["now"], files.get("nam"))
    write_file(name, lines)

def run():
    parse_file('variants.html', parse_variants)

if __name__ == "__main__":
    run()
    #homes, borders = parse_definition(open("hundred3.mdf"))
    #print "Borders:", borders
    #print "Homes:", homes
