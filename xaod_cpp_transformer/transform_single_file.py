#  Copyright (c) 2022 , IRIS-HEP
#   All rights reserved.
#
#   Redistribution and use in source and binary forms, with or without
#   modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice, this
#     list of conditions and the following disclaimer.
#
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#
#   * Neither the name of the copyright holder nor the names of its
#     contributors may be used to endorse or promote products derived from
#     this software without specific prior written permission.
#
#   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#   AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#   IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#   DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#   FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#   DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#   SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#   CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#   OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#   OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#
#
#
import os
import sys
import re
import logging
import uproot

def parse_output_logs(logger, logfile):
    """
    Parse output from runner.sh and output appropriate log messages
    :param logfile: path to logfile
    :return:  Tuple with (total_events: Int, processed_events: Int)
    """
    total_events = 0
    events_processed = 0
    total_events_re = re.compile(r'Processing events \d+-(\d+)')
    events_processed_re = re.compile(r'Processed (\d+) events')
    with open(logfile, 'r') as f:
        buf = f.read()
        match = total_events_re.search(buf)
        if match:
            total_events = int(match.group(1))
        matches = events_processed_re.finditer(buf)
        for m in matches:
            events_processed = int(m.group(1))
        logger.info("{} events processed out of {} total events".format(
            events_processed, total_events))
    return total_events, events_processed

def transform_single_file(file_path, output_path, logger):
    """
    Transform a single file and return some information about output
    :param file_path: path for file to process
    :param output_path: path to file
    :param servicex: servicex instance
    :return: Tuple with (total_events: Int, output_size: Int)
    """


    logger.info("Transforming a single path: {} into {}".format(file_path, output_path))

    r = os.system('bash /generated/runner.sh -r -d ' + file_path +
                  ' -o ' + output_path + '| tee {lf}'.format(lf=logfile))
    # This command is not available in all images!
    # os.system('/usr/bin/sync log.txt')
    total_events, _ = parse_output_logs(logger, logfile)
    output_size = 0
    if os.path.exists(output_path) and os.path.isfile(output_path):
        output_size = os.stat(output_path).st_size
        logger.info("Wrote {} bytes after transforming {}".format(output_size, file_path))

    reason_bad = None
    if r != 0:
        reason_bad = "Error return from transformer: " + str(r)
    if (reason_bad is None) and not os.path.exists(output_path):
        reason_bad = "Output file " + output_path + " was not found"
    if reason_bad is not None:
        with open('log.txt', 'r') as f:
            errors = f.read()
            mesg = "Failed to transform input file {}: ".format(file_path) + \
                   "{} -- errors: {}".format(reason_bad, errors)
        logger.error(mesg)
        raise RuntimeError(mesg)

    return total_events, output_size


def compile_code(logger,logfile):
    # Have to use bash as the file runner.sh does not execute properly, despite its 'x'
    # bit set. This seems to be some vagary of a ConfigMap from k8, which is how we usually get
    # this file.
    r = os.system('bash /generated/runner.sh -c | tee {lf}'.format(lf=logfile))
    if r != 0:
        with open('log.txt', 'r') as f:
            errors = f.read()
            logger.error("Unable to compile the code - error return: " +
                         str(r) + 'errors: ' + errors)
            raise RuntimeError("Unable to compile the code - error return: " +
                               str(r) + "errors: \n" + errors)


if __name__ == '__main__':
    file_path = sys.argv[1]
    output_path = sys.argv[2]
    logfile = os.path.join(output_path, 'transform.log')
    logging.basicConfig(filename= logfile,
                        level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    logger = logging.getLogger(file_path)
    compile_code(logger,logfile)
    transform_single_file(file_path, output_path, logger)
