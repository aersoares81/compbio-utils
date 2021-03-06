#!/usr/bin/env python
"""Score an alignment

Implement gap handling and more scores:
http://www.biostars.org/post/show/3856/entropy-from-a-multiple-sequence-alignment-with-gaps/

William Valdar : Scoring Residue Conservation.
http://onlinelibrary.wiley.com/doi/10.1002/prot.10146/abstract;jsessionid=18D6E98A259624E3D6616386C0EC32C5.d03t02

Output is a table with one row per alignment column:
1. pos
2. identity
3. entropy
4. basecounts as base:count tuples
"""


#--- standard library imports
#
import os
import sys
from math import log
import logging
# optparse deprecated from Python 2.7 on
from optparse import OptionParser
from collections import Counter

#--- third-party imports
#
from Bio import AlignIO

#--- project specific imports
#
import bioutils

# invocation of ipython on exceptions
if False:
    import sys, pdb
    from IPython.core import ultratb
    sys.excepthook = ultratb.FormattedTB(
        mode='Verbose', color_scheme='Linux', call_pdb=1)

        
__author__ = "Andreas Wilm"
__version__ = "0.1"
__email__ = "andreas.wilm@gmail.com"
__license__ = "The MIT License (MIT)"


#global logger
# http://docs.python.org/library/logging.html
LOG = logging.getLogger("")
logging.basicConfig(level=logging.WARN,
                    format='%(levelname)s [%(asctime)s]: %(message)s')

        
                
def shannon_entropy(l, b=2):
    """Return the Shannon entropy of random variable with probability
    vector l.

    Adopted from
    http://www.lysator.liu.se/~jc/mthesis/A_Source_code.html#functiondef:entropies.py:shannon_entropy
    """
    return sum([-p*log(p, b) for p in l if p > 0])

    
def cmdline_parser():
    """
    creates an OptionParser instance
    """

    # http://docs.python.org/library/optparse.html
    usage = "%prog: " + __doc__ + "\n" \
            "usage: %prog [options]"
    parser = OptionParser(usage=usage)

    parser.add_option("", "--verbose",
                      action="store_true", dest="verbose",
                      help="be verbose")
    parser.add_option("", "--debug",
                      action="store_true", dest="debug",
                      help="debugging")
    parser.add_option("-i", "--aln",
                      dest="aln_in",
                      help="Input alignment or '-' for stdin")
    parser.add_option("-m", "--map-to",
                      dest="map_to",
                      help="If given, using unaligned positions of this"
                      " seq instead of aligned pos (skipping pos with gaps in this seq)")
    return parser


def seqid(colctr):
    """colctr has to be collections.Counter for residues in an
    alignment column
    """
    for (res, count) in colctr.most_common():
        if res not in bioutils.GAP_CHARS:
            return count/float(sum(colctr.values()))
    # can only happen if only gaps
    return 0.0    


def get_aln_column(aln, col_no):
    """Replacement for depreacted Alignment.get_column()
    """
    assert col_no < aln.get_alignment_length() 
    # get_column() and get_all_seq() deprecated
    return ''.join([s.seq[col_no] for s in aln])


def unaln_pos_map(seq):
    """Returns a list of length seq, where each value contains the
    unaligned position (or None if NA)
    """
    map_to_seq_cols = []
    gap_ctr = 0
    for i in range(len(seq)):
        if seq[i] in bioutils.GAP_CHARS:
            gap_ctr += 1
        map_to_seq_cols.append(i-gap_ctr)
        if map_to_seq_cols[-1] < 0:
            map_to_seq_cols[-1] = None
    return map_to_seq_cols


def main():
    """
    The main function
    """

    parser = cmdline_parser()
    (opts, args) = parser.parse_args()

    if opts.verbose:
        LOG.setLevel(logging.INFO)
    if opts.debug:
        LOG.setLevel(logging.DEBUG)
    if not opts.aln_in:
        parser.error("Missing input alignment argument\n")
        sys.exit(1)
    if len(args):
        parser.error("Unrecognized arguments found: %s" % args)
        
    char_set = "ACGTU"
    char_set = "ACDEFGHIKLMNPQRSTVWY"
    #x = any
    #z = Gln or Glu
    #b = Asp or Asn
    char_set = "ACGTN"

    LOG.warn("using hardcoded charset %s" % char_set)
    # FIXME auto-detection of alphabet)
    
    if opts.aln_in != "-" and not os.path.exists(opts.aln_in):
        LOG.fatal("Input alignment %s does not exist.\n" % opts.aln_in)
        sys.exit(1)

    if opts.aln_in == "-":
        fh = sys.stdin
        fmt = 'fasta'
    else:
        fmt = bioutils.guess_seqformat(opts.aln_in)
        fh = open(opts.aln_in, "rU")
                
    entropy_per_col = []    
    seqid_per_col = []    
    # note: had one case where this happily read an unaligned file!?
    aln = AlignIO.read(fh, fmt)

    # if requested, get sequence record for the sequence we should
    # positions to
    map_to_seq = None
    if opts.map_to:
        map_to_seq = [rec.seq for rec in aln if rec.id == opts.map_to]
        if not len(map_to_seq):
            LOG.fatal("Couldn't find a sequence called %s in %s" % (
                opts.map_to, fh.name))
            sys.exit(1)
        elif len(map_to_seq)>1:
            LOG.fatal("Find more than one sequence with name %s in %s" % (
                opts.map_to, fh.name))
            sys.exit(1)
        map_to_seq = map_to_seq[0]
        map_to_seq_cols = unaln_pos_map(map_to_seq)
        
    for i in xrange(aln.get_alignment_length()):
        #col = aln.get_column(i) # deprecated
        col = get_aln_column(aln, i).upper()
        not_in_char_set = [c for c in col if c not in char_set]
        not_in_char_set = [c for c in not_in_char_set if c not in bioutils.GAP_CHARS]        
        if len(not_in_char_set):
            LOG.warn("Found characters not in char_set (%s) in col %d (%s)" % (
                char_set, i+1, set(not_in_char_set)))
        counter = Counter(col)

        vec = []
        # this will ignore invalid chars incl. ambiguities        
        denom = sum([counter[r] for r in char_set])
        if denom == 0:
            LOG.fatal("denom = 0, means no valid chars in col %d?" % (i+1))
            #import pdb; pdb.set_trace()
            raise ValueError
        for res in char_set:
            vec.append(counter[res]/float(denom))
        LOG.debug("vec=%s denom=%s counter=%s" % (vec, denom, counter))
        entropy_per_col.append(shannon_entropy(vec))

        seqid_per_col.append(seqid(counter))

        # due to the fact that we keep all values (which is actually
        # not necessary but would come in handy if values were
        # precalculated) we cannot simply continue or there would be
        # some missing. 'continue/next' here if needed.
        if map_to_seq and map_to_seq[i] in bioutils.GAP_CHARS:
            LOG.debug("Skipping col %d because map_to_seq has gap there." % (i+1))
            continue

        counts_str = ' '.join(
            ["%s:%d" % (k,v) for (k,v) in sorted(counter.iteritems())])
        if not map_to_seq:
            rep_col = i
        else: 
            rep_col = map_to_seq_cols[i]
        print "%d %.6f %.6f %s" % (
            rep_col+1 if not map_to_seq else map_to_seq_cols[i]+1, 
            seqid_per_col[i], entropy_per_col[i], counts_str)

    if fh != sys.stdout:
        fh.close()

        
if __name__ == "__main__":
    main()


