#read coverage from files

import vu_common as CM
def parseFilename(tree, covered, uncovered):
    assert tree.tag == "class", tree.tag
    assert set(tree.attrib) == {'branch-rate', 'complexity', 'line-rate', 'name', 'filename'}, tree.attrib
    
    filename = tree.attrib['filename']
    for lines in tree:
        assert lines.tag in {"methods", "lines"}, lines.tag
        assert not lines.attrib, lines.attrib

        for line in lines:
            assert line.tag == "line", line.tag
            assert set(line.attrib) == set(['hits', 'number']), line.attrib

            lineno = line.attrib["number"]
            nhits = int(line.attrib['hits'])
            cline = "{}:{}".format(filename, lineno)
            if nhits >= 1:
                covered.add(cline)
            else:
                assert nhits == 0, nhits
                uncovered.add(cline)

def parse(xmlfile):
    covered = set()
    uncovered = set()
    
    import xml.etree.ElementTree
    tree = xml.etree.ElementTree.parse(xmlfile)
    root = tree.getroot()
    for child in root:
        assert child.tag == "packages", child.tag
        assert not child.attrib, child.attrib
        for child1 in child:
            assert child1.tag == "package", child1.tag
            assert set(child1.attrib) == {'branch-rate', 'complexity', 'line-rate', 'name'}, child1.attrib
            for child2 in child1:
                assert child2.tag == "classes", child2.tag
                assert not child2.attrib, child2.attrib
                for child3 in child2:
                    parseFilename(child3, covered, uncovered)
                
    return covered, uncovered


def cleanup(lines):
    """
    clean up resulting format
    E.g., dir/file,cover:n  ->  file:n
    """
    import os.path
    hashd = {}
    lines_ = set()
    for l in lines:
        ldir = os.path.dirname(l)
        lfile =  os.path.basename(l)
        if ldir not in hashd:
            hashd[ldir] = ''.join(s[0] for s in ldir.split("/") if s)
            
        lines_.add("{}/{}".format(hashd[ldir],lfile))
    
    return lines_
    
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("xml", help="xml cov file")
    args = parser.parse_args()

    covered, uncovered = parse(args.xml)
    print '{} covered lines'.format(len(covered))
    covered = cleanup(covered)
    print '{} covered lines'.format(len(covered))
    print '\n'.join(sorted(covered))

    print '{} uncovered lines'.format(len(uncovered))
    #print '\n'.join(sorted(uncovered))
    
