#!/usr/bin/python3.11
# Copyright (c) 2019, IRIS-HEP
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import argparse
import logstash
import logging
import os
import sys

from servicex_storage import s3_storage_manager

instance = os.environ.get('INSTANCE_NAME', 'Unknown')


class StreamFormatter(logging.Formatter):
    """
    A custom formatter that adds extras.
    Normally log messages are "level instance component msg extra: {}"
    """
    def_keys = ['name', 'msg', 'args', 'levelname', 'levelno',
                'pathname', 'filename', 'module', 'exc_info',
                'exc_text', 'stack_info', 'lineno', 'funcName',
                'created', 'msecs', 'relativeCreated', 'thread',
                'threadName', 'processName', 'process', 'message']

    def format(self, record: logging.LogRecord) -> str:
        """
        :param record: LogRecord
        :return: formatted log message
        """

        string = super().format(record)
        extra = {k: v for k, v in record.__dict__.items()
                 if k not in self.def_keys}
        if len(extra) > 0:
            string += " extra: " + str(extra)
        return string


class LogstashFormatter(logstash.formatter.LogstashFormatterBase):

    def format(self, record):
        message = {
            '@timestamp': self.format_timestamp(record.created),
            '@version': '1',
            'message': record.getMessage(),
            'path': record.pathname,
            'tags': self.tags,
            'type': self.message_type,
            'instance': instance,
            'component': 'minio cleaner',

            # Extra Fields
            'level': record.levelname,
            'logger_name': record.name,
        }

        # Add extra fields
        message.update(self.get_extra_fields(record))

        # If exception, add debug info
        if record.exc_info:
            message.update(self.get_debug_fields(record))

        return self.serialize(message)


# function to initialize logging
def initialize_logging() -> logging.Logger:
    """
    Get a logger and initialize it so that it outputs the correct format

    :return: logger with correct formatting that outputs to console
    """

    log = logging.getLogger()
    formatter = logging.Formatter('%(levelname)s ' +
                                  f"{instance} minio cleaner " +
                                  + '%(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    return log


def strtobool(val: str) -> bool:
    """Convert a string representation of truth to true (1) or false (0).

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    val = val.lower()
    if val in ('y', 'yes', 't', 'true', 'on', '1'):
        return True
    elif val in ('n', 'no', 'f', 'false', 'off', '0'):
        return False
    else:
        raise ValueError("invalid truth value %r" % (val,))


def parse_suffix(size: str) -> int:
    """
    Take a string like 100M or 20G or 30T and return an integer
    number of bytes that string represents

    raises ValueError if
    :param size: a string with a M, G, T suffix indicating size
    :return: integer number of bytes
    """
    if size[-1] in ['M', 'G', 'T']:  # process suffix
        raw_max = float(size[:-1])
        mult = size[-1]
        if mult == 'M':
            raw_max *= 2 ** 20
        elif mult == 'G':
            raw_max *= 2 ** 30
        elif mult == 'T':
            raw_max *= 2 ** 40
        else:
            raise ValueError
        return int(raw_max)
    else:
        return int(size)


def run_minio_cleaner():
    """
    Run the minio cleaner
    """

    # Parse the command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-size', dest='max_size', action='store',
                        default='',
                        help='Max size allowed before pruning storage')
    parser.add_argument('--norm-size', dest='norm_size', action='store',
                        default='',
                        help='Size to prune storage to')
    parser.add_argument('--max-age', dest='max_age', action='store',
                        default=30,
                        type=int,
                        help='Max age of files in days allowed before pruning storage')

    logstash_host = os.environ.get('LOGSTASH_HOST')
    logstash_port = os.environ.get('LOGSTASH_PORT')
    level = os.environ.get('LOG_LEVEL', 'INFO').upper()

    stream_handler = logging.StreamHandler()
    stream_formatter = StreamFormatter('%(levelname)s ' +
                                       f"{instance} minio_cleanup " +
                                       '%(message)s')
    stream_handler.setFormatter(stream_formatter)
    stream_handler.setLevel(level)
    logger.addHandler(stream_handler)

    if logstash_host and logstash_port:
        logstash_handler = logstash.TCPLogstashHandler(logstash_host, logstash_port, version=1)
        logstash_formatter = LogstashFormatter('logstash', None, None)
        logstash_handler.setFormatter(logstash_formatter)
        logstash_handler.setLevel(level)
        logger.addHandler(logstash_handler)

    args = parser.parse_args()
    try:
        raw_max = parse_suffix(args.max_size)
    except ValueError:
        logger.error(f"Can't parse max size, got: {args.max_size}")
        sys.exit(1)
    try:
        raw_norm = parse_suffix(args.norm_size)
    except ValueError:
        logger.error(f"Can't parse norm size, got: {args.norm_size}")
        sys.exit(1)

    logger.info("ServiceX Minio Cleaner starting up.")

    env_vars = ['MINIO_URL', 'ACCESS_KEY', 'SECRET_KEY']
    error = False
    for var in env_vars:
        if var not in os.environ:
            logger.error(f"{var} not found in environment")
            error = True
    if error:
        logger.error("Exiting due to missing environment variables")
        sys.exit(1)

    try:
        if 'MINIO_ENCRYPT' in os.environ:
            if isinstance(os.environ['MINIO_ENCRYPT'], bool):
                use_https = os.environ['MINIO_ENCRYPT']
            else:
                use_https = strtobool(os.environ['MINIO_ENCRYPT'])
        else:
            use_https = False

        store = s3_storage_manager.S3Store(s3_endpoint=os.environ['MINIO_URL'],
                                           access_key=os.environ['ACCESS_KEY'],
                                           secret_key=os.environ['SECRET_KEY'],
                                           use_https=use_https)
        logger.info("cleanup started")
        results = store.cleanup_storage(max_size=raw_max, norm_size=raw_norm, max_age=args.max_age)
        logger.info("cleanup stopped finished.", extra={
                    "storage used": results[0],
                    "storage available": raw_max,
                    "storage HWM": raw_norm})
        for bucket in results[1]:
            logger.info(f"Removed folder/bucket: {bucket}")
        logger.info("Deleted buckets", extra={'nbuckets': len(results[1])})
    finally:
        logger.info('Done running minio storage cleanup')


if __name__ == "__main__":
    logger = initialize_logging()
    run_minio_cleaner()
