#!/usr/bin/env python
"""A grep for sequence files
"""


#--- standard library imports
#
import os
import sys
import logging
# optparse deprecated from Python 2.7 on
from optparse import OptionParser
import re

#--- third-party imports
#
from Bio import SeqIO

#--- project specific imports
#
# /

                                                        
__author__ = "Andreas Wilm"
__version__ = "0.1"
__email__ = "wilma@gis.a-star.edu.sg"
__copyright__ = ""
__license__ = ""
__credits__ = [""]
__status__ = ""


#global logger
# http://docs.python.org/library/logging.html
LOG = logging.getLogger("")
logging.basicConfig(level=logging.WARN,
                    format='%(levelname)s [%(asctime)s]: %(message)s')


def guess_seqformat(fseq):
    """
    FIXME
    """
    default = 'fasta'

    # Table for guessing the alignment format from the file extension. 
    # See http://www.biopython.org/wiki/SeqIO
    #
    # Only define the ones I actually came accors here:
    ext_to_fmt_table = dict(
        aln = 'clustal',
        embl = 'embl',
        fasta = 'fasta',
        fa = 'fasta',
        genbank = 'genbank',
        gb = 'genbank',
        phylip = 'phylip',
        phy = 'phylip',
        ph = 'phylip',
        pir = 'pir',
        stockholm = 'stockholm',
        st = 'stockholm',
        stk = 'stockholm')

    try:
        fext = os.path.splitext(fseq)[1]
        fext = fext[1:].lower()
        fmt =  ext_to_fmt_table[fext]
    except KeyError:
        return default
    return fmt


def cmdline_parser():
    """
    creates an OptionParser instance
    """

    # http://docs.python.org/library/optparse.html
    usage = "%prog: " + __doc__ + "\n" \
            "usage: %prog [options]"
    parser = OptionParser(usage=usage)

    parser.add_option("-s", "--search-in",
                      dest="search_in",
                      default="id", choices=['seq', 'id'],
                      help="Search in sequence or its name")
    parser.add_option("", "--verbose",
                      action="store_true", dest="verbose",
                      help="be verbose")
    parser.add_option("", "--debug",
                      action="store_true", dest="debug",
                      help="debugging")
    #parser.add_option("-c", "--case",
    #                  action="store_true", dest="case",
    #                  help="Make search case sensitive")
    parser.add_option("-v", "--invert-match",
                      action="store_true", dest="invert_match",
                      help="invert sense of matching")
    return parser


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
        
    if len(args)<2:
        parser.error("Need pattern and at least one seqfile as argument")
        sys.exit(1)

    
    # first arg is pattern. rest are files
    pattern_arg = args[0]
    seqfiles_arg = args[1:]
    LOG.debug("args=%s" % (args))
    LOG.debug("pattern_arg=%s" % (pattern_arg))
    LOG.debug("seqfiles_arg=%s" % (seqfiles_arg))

    regexp = re.compile(pattern_arg)

    for fseq in seqfiles_arg:
        if not fseq != "" and os.path.exists(fseq):
            LOG.fatal("input file %s does not exist.\n" % fseq)
            sys.exit(1)

    for fseq in seqfiles_arg:
        if fseq == "-":
            fhandle = sys.stdin
        else:
            fhandle = open(fseq, "rU")
        
        fmt = guess_seqformat(fseq)
        if not fmt:
            fmt = 'fasta'
            
        for record in SeqIO.parse(fhandle, fmt):
            #LOG.debug("checking seq %s (len %d)" % (record.id, len(record.seq)))

            if opts.search_in == 'seq':
                target = record.seq
            elif opts.search_in == 'id':
                # special case fasta: id is everything before the
                # first whitespace. description contains this as well.
                if fmt == 'fasta':
                    target = record.description
                else:
                    target = record.id
            else:
                raise ValueError, (
                    "internal error...not sure where to search in")

            match = regexp.search(target) 
            #import pdb; pdb.set_trace()
            print_match = False
            if match and not opts.invert_match:
                LOG.debug("match.string=%s" % match.string)
                print_match = True
            elif opts.invert_match and not match:
                print_match = True

            if print_match:
                if fmt == 'fasta':
                    print ">%s\n%s" % (record.description, record.seq)
                else:
                    print ">%s\n%s" % (record.id, record.seq)
        if fhandle != sys.stdin:
            fhandle.close()


if __name__ == "__main__":
    main()
    LOG.debug("FIXME: Allow for other filter opts, e.g. length, case-indep., support output format arg.")

