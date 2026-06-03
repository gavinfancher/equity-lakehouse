from dagster import Definitions

from finpipe.assets import ingest

defs = Definitions(assets=[ingest])
