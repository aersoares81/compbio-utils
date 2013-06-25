#!/usr/bin/env python
"""Report joined nucleotide frequencies for given positions. Positions
 have to be on the same read or in a read pair, for it to be counted
 """


#--- standard library imports
#
import sys
import os
import logging
import argparse

#--- third-party imports
#
import pysam


#--- project specific imports
#
# /


__author__ = "Andreas Wilm"
__version__ = "0.1"
__email__ = "andreas.wilm@gmail.com"
__license__ = "The MIT License (MIT)"


# global logger
# http://docs.python.org/library/logging.html
LOG = logging.getLogger("")
logging.basicConfig(level=logging.WARN, 
                    format='%(levelname)s [%(asctime)s]: %(message)s')


def cmdline_parser():
    """
    creates an argparse instance
    """

    # http://docs.python.org/library/optparse.html
    parser = argparse.ArgumentParser(
        description=__doc__)

    parser.add_argument("--verbose",
                      dest="verbose",
                      action="store_true",
                      help="Enable verbose output")
    parser.add_argument("--debug",
                      dest="debug",
                      action="store_true", 
                      help=argparse.SUPPRESS) #"debugging")
    
    parser.add_argument("-b", "--bam",
                      dest="bam",
                      required=True,
                      help="Mapping input file (BAM)")
    parser.add_argument('-c", "--chrom', 
                        dest="chrom",
                        required="chrom",
                        help="Positions are on this chromomsome/sequence")
    parser.add_argument('-p", "--positions', 
                        dest="positions",
                        metavar='NN',
                        type=int,
                        required=True,
                        nargs='+',
                        help='List of positions')

    parser.add_argument("-f", "--fasta",
                        dest="ref_fa",
                        help="Will print bases at given positions in"
                        " reference fasta file")
    parser.add_argument("-m", "--min-mq",
                        dest="min_mq",
                        type=int,
                        default=13,
                        help="Ignore reads with MQ smaller than this value")

    return parser



def joined_counts(sam, chrom, positions, min_mq=13):
    """sam: samfile object (pysam)
    chrom: chromsome/sequence of interest
    positions: list of (zero-offset) positions to analyze (note, use long if necessary)
    min_mq:filter reads with mapping qualiy below this value
    
    Note, will only report counts that overlap *all* positions.
    """

    assert len(positions)>=2 and min(positions)>=0
    
    num_dups = 0
    num_anomalous = 0
    num_qcfail = 0
    num_secondary = 0
    num_below_mq_min = 0
    # FIXME put the above into one namedtuple
    
    pos_overlap = dict()

    # NOTE: we actually don't really need to fetch all pos. one after
    # max should be enough. but what if circular? best to be on the
    # safe side. For full control over BQ, BAQ etc we would have to
    # use mpileup() instead of fetch().

    for alnread in sam.fetch(chrom, min(positions), max(positions)+1):
        assert not alnread.is_unmapped # paranoia

        if alnread.is_duplicate:
            num_dups += 1
            continue
        
        if alnread.is_paired and not alnread.is_proper_pair:
            # check both as is_proper_pair might contain nonsense
            # value if not paired
            num_anomalous += 1
            continue

        if alnread.is_qcfail:
            num_qcfail += 1
            continue

        if alnread.is_secondary:
            num_secondary += 1
            continue

        if alnread.mapq < min_mq:
            num_below_mq_min += 1
            continue
            

        # create a map of ref position (key; long int(!)) and the
        # corresponding query (clipped read) nucleotides (value)
        pos_nt_map = dict([(rpos, alnread.query[qpos])
                           for (qpos, rpos) in alnread.aligned_pairs 
                           if qpos!=None and rpos!=None])
                           # can't just use if qpos and rpos since
                           # they might be 0
                           
        # create read-id which is identical for PE reads. NOTE: is
        # there another way to identify pairs? Using the name only is
        # a weakness and might lead to silent errors
        if alnread.qname[-2] in [".", "/", "#"]:
            read_id_base = alnread.qname[:-2]
        else:
            read_id_base = alnread.qname

        # record read-id (same for PE reads) and nucleotide for each
        # given position
        for pos in positions:
            if pos_nt_map.has_key(pos):
                if not pos_overlap.has_key(pos):
                    pos_overlap[pos] = dict()
                pos_overlap[pos][read_id_base] = pos_nt_map[pos]

    # create a list of read-id's overlapping all given pos
    overlapping_all = frozenset(pos_overlap[positions[0]].keys())
    for pos in positions[1:]:
        overlapping_all = overlapping_all.intersection(
            pos_overlap[pos].keys())
    overlapping_all = list(overlapping_all)

    counts = dict()
    for read_id in overlapping_all:
        key = ''.join([pos_overlap[p][read_id] for p in positions])
        counts[key] = counts.get(key, 0) + 1
    
    LOG.info("Ignored %d paired-end reads flagged as not in proper"
             "  pair" % (num_anomalous))
    LOG.info("Ignored %d reads flagged as duplicates" % (num_dups))
    LOG.info("Ignored %d reads flagged as qc fail" % (num_qcfail))
    LOG.info("Ignored %d reads flagged as secondary" % (num_secondary))
    LOG.info("Ignored %d reads below MQ threshold (%d)" % (num_below_mq_min, min_mq))

    counts_sum = sum(counts.values())
    LOG.info("%d reads overlapped with given positions %s"  % (
        counts_sum, ''.join([str(x+1) for x in positions])))

    return counts


    
def main():
    """
    The main function
    """

    parser = cmdline_parser()
    args = parser.parse_args()
    
    if args.verbose:
        LOG.setLevel(logging.INFO)
    if args.debug:
        LOG.setLevel(logging.DEBUG)
        
    # file check
    if not os.path.exists(args.bam):
        LOG.fatal("file '%s' does not exist.\n" % args.bam)
        sys.exit(1)
    if args.ref_fa and not os.path.exists(args.ref_fa):
        LOG.fatal("file '%s' does not exist.\n" % args.ref_fa)
        sys.exit(1)

    positions = [x-1 for x in args.positions]
    if len(positions) < 2:
        LOG.fatal("Need at least two positions of interest")
        parser.print_usage(sys.stderr)
        sys.exit(1)
    if any([pos < 0 for pos in positions]):
        LOG.fatal("Positions need to be >=1")
        parser.print_usage(sys.stderr)
        sys.exit(1)
    LOG.critical("Check if any positions >(=?) ref length")

    if args.ref_fa:
        fastafile = pysam.Fastafile(args.ref_fa)
        for pos in positions:
            # region = "%s:%d-%d" % (args.chrom, pos+1, pos+1)
            # region needs +1 again which is not intuitive
            # refbase = fastafile.fetch(region=region)
            refbase = fastafile.fetch(args.chrom, pos, pos+1)
            if not refbase:
                LOG.fatal("Couldn't fetch region from fastafile %s."
                          " Possible chromsome/sequence name"
                          " mismatch" % (args.ref_fa))
            print "Reference at pos %d: %s" % (pos+1, refbase)
            
    sam = pysam.Samfile(args.bam, "rb")

    counts = joined_counts(sam, args.chrom, positions, args.min_mq)
    counts_sum = sum(counts.values())
    for k in sorted(counts.keys()):
        if counts[k]:
            print "%s %d %.4f" % (k, counts[k], counts[k]/float(counts_sum))

    
if __name__ == "__main__":
    LOG.critical("TEST: MQ filter, position overlap, counts etc")
    main()
    LOG.info("Successful exit")
