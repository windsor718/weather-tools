"""Primary ECMWF Downloader Workflow."""

import argparse
import io
import itertools
import logging
import os
import tempfile
import typing as t

import apache_beam as beam
import apache_beam.metrics
from apache_beam.options.pipeline_options import PipelineOptions, SetupOptions
from apache_beam.io.gcp import gcsio
import cdsapi

from ecmwf_pipeline.parsers import process_config


def prepare_partition(config: t.Dict) -> t.Iterator[t.Dict]:
    """Iterate over client parameters, partitioning over `partition_keys`."""
    partition_keys = config['parameters']['partition_keys']
    selection = config.get('selection', {})

    # Produce a Cartesian-Cross over the range of keys.
    # For example, if the keys were 'year' and 'month', it would produce
    # an iterable like: ( ('2020', '01'), ('2020', '02'), ('2020', '03'), ...)
    fan_out = itertools.product(*[selection[key] for key in partition_keys])

    # Output a config dictionary, overriding the range of values for
    # each key with the partition instance in 'selection'.
    # Continuing the example:
    #   { 'foo': ..., 'year': ['2020'], 'month': ['01'], ... }
    #   { 'foo': ..., 'year': ['2020'], 'month': ['02'], ... }
    #   { 'foo': ..., 'year': ['2020'], 'month': ['03'], ... }
    for option in fan_out:
        copy = selection.copy()
        out = config.copy()
        for idx, key in enumerate(partition_keys):
            copy[key] = [option[idx]]
        out['selection'] = copy
        yield out


def fetch_data(config: t.Dict) -> t.Tuple[str, io.BytesIO]:
    """Download data from a client."""
    dataset = config['parameters']['dataset']

    partition_keys = config['parameters']['partition_keys']
    partition_key_values = [config['selection'][key][0] for key in partition_keys]
    target = config['parameters']['target_template'].format(*partition_key_values)

    selection = config['selection']

    client = cdsapi.Client(
        url=config['parameters'].get('api_url', os.environ.get('CDSAPI_URL')),
        key=config['parameters'].get('api_key', os.environ.get('CDSAPI_KEY')),
    )

    with tempfile.NamedTemporaryFile() as temp:
        try:
            logging.info('Fetching data for target {}'.format(target))
            client.retrieve(dataset, selection, temp.name)
            beam.metrics.Metrics.counter('Success', 'FetchData').inc()
            temp.seek(0)
            return target, io.BytesIO(temp.read())
        except Exception as e:
            logging.error('Unable to retrieve data for {}: {}'.format(target, e))
            beam.metrics.Metrics.counter('Failure', 'FetchData').inc()
            return '', io.BytesIO()


def write_data(target: str, data: io.BytesIO) -> None:
    """Write artifacts to Google Cloud Storage."""
    if not target:
        return

    with gcsio.GcsIO().open(target, 'wb') as f:
        f.write(data.read())


def run(argv: t.List[str], save_main_session: bool = True):
    """Main entrypoint & pipeline definition."""
    parser = argparse.ArgumentParser()
    parser.add_argument('config', type=argparse.FileType('r', encoding='utf-8'),
                        help='path/to/config.cfg, specific to the <client>. Accepts *.cfg and *.json files.')
    parser.add_argument('-c', '--client', type=str, choices=['cdn'], default='cdn',
                        help="Choose a weather API client; default is 'cnd'.")

    known_args, pipeline_args = parser.parse_known_args(argv[1:])

    config = {}
    with known_args.config as f:
        config = process_config(f)

    # We use the save_main_session option because one or more DoFn's in this
    # workflow rely on global context (e.g., a module imported at module level).
    pipeline_options = PipelineOptions(pipeline_args)
    pipeline_options.view_as(SetupOptions).save_main_session = save_main_session

    with beam.Pipeline(options=pipeline_options) as p:
        output = (
                p
                | 'Create' >> beam.Create(prepare_partition(config))
                | 'FetchData' >> beam.Map(fetch_data)
                | 'WriteData' >> beam.MapTuple(write_data)
        )
