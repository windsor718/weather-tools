import argparse
import logging
import os
import typing as t

import apache_beam as beam
from apache_beam.io.fileio import MatchFiles, ReadMatches
import apache_beam.metrics as metrics
from apache_beam.options.pipeline_options import PipelineOptions, SetupOptions

from .file_splitters import get_splitter


def configure_logger(verbosity: int) -> None:
    """Configures logging from verbosity. Default verbosity will show errors."""
    logging.basicConfig(level=(40 - verbosity * 10),
                        format='%(asctime)-15s %(message)s')


def split_file(input_file: str, input_base_dir: str, output_directory: str, dry_run: bool):
    logging.info('Splitting file %s', input_file)
    metrics.Metrics.counter('pipeline', 'splitting file').inc()
    splitter = get_splitter(input_file,
                            get_output_base_name(input_path=input_file,
                                                 input_base=input_base_dir,
                                                 output_dir=output_directory),
                            dry_run)
    splitter.split_data()


def _get_base_input_directory(input_pattern: str) -> str:
    base_dir = input_pattern
    for x in ['*', '?', '[']:
        base_dir = base_dir.split(x, maxsplit=1)[0]
    # Go one directory up to include the last common directory in output path.
    return os.path.dirname(os.path.dirname(base_dir))


def get_output_base_name(input_path: str, input_base: str,
                         output_dir: str) -> str:
    return input_path.replace(input_base, output_dir)


def run(argv: t.List[str], save_main_session: bool = True):
    """Main entrypoint & pipeline definition."""
    parser = argparse.ArgumentParser(
        prog='weather-splitter',
        description='Split weather data file into files by variable.'
    )
    parser.add_argument('-i', '--input_pattern', type=str, required=True,
                        help='Pattern for input weather data.')
    parser.add_argument('-o', '--output_dir', type=str, required=True,
                        help='Path to base folder for output files. '
                        'This directory will replace the common path of the '
                        'input_pattern. For `input_pattern a/b/c/**` and '
                        '`output_dir /x/y/z` a file `a/b/c/file.nc` will create'
                        'output files like `/x/y/z/c/file.nc_shortname.nc`'
                        )
    parser.add_argument('-d', '--dry_run', action='store_true', default=False,
                        help='Test the input file matching and the output file scheme without splitting.')
    known_args, pipeline_args = parser.parse_known_args(argv[1:])

    configure_logger(3)  # 0 = error, 1 = warn, 2 = info, 3 = debug

    pipeline_options = PipelineOptions(pipeline_args)
    pipeline_options.view_as(SetupOptions).save_main_session = save_main_session
    input_pattern = known_args.input_pattern
    input_base_dir = _get_base_input_directory(known_args.input_pattern)
    # output target directory, if empty, set to same as input
    output_directory = known_args.output_dir
    if not output_directory:
        output_directory = input_base_dir
    dry_run = known_args.dry_run

    logging.debug('input_pattern: %s', input_pattern)
    logging.debug('input_base_dir: %s', input_base_dir)
    logging.debug('output_directory: %s', output_directory)
    logging.debug('dry_run: %s', known_args.dry_run)
    with beam.Pipeline(options=pipeline_options) as p:
        (
            p
            | 'MatchFiles' >> MatchFiles(input_pattern)
            | 'ReadMatches' >> ReadMatches()
            | 'Shuffle' >> beam.Reshuffle()
            | 'GetPath' >> beam.Map(lambda x: x.metadata.path)
            | 'SplitFiles' >> beam.Map(split_file,
                                       input_base_dir,
                                       output_directory,
                                       dry_run)
        )
