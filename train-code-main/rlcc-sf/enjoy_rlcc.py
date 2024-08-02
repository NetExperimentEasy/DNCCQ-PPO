from sample_factory.enjoy import enjoy

import sys

from sample_factory.cfg.arguments import parse_full_cfg, parse_sf_args
from sample_factory.envs.env_utils import register_env
from sample_factory.train import run_rl
from rlcc_utils import add_rlcc_env_args, rlcc_override_defaults
from rlcc_utils import RLCC_ENVS, make_rlcc_env

def register_rlcc_components():
    for env in RLCC_ENVS:
        register_env(env.name, make_rlcc_env)


def parse_rlcc_cfg(argv=None, evaluation=False):
    parser, partial_cfg = parse_sf_args(argv=argv, evaluation=evaluation)
    add_rlcc_env_args(partial_cfg.env, parser)
    rlcc_override_defaults(partial_cfg.env, parser)
    final_cfg = parse_full_cfg(parser, argv)
    return final_cfg


def main():  # pragma: no cover
    """Script entry point."""
    register_rlcc_components()
    cfg = parse_rlcc_cfg(evaluation=True)

    state_queue = 

    status = enjoy(cfg, input_queue)
    return status


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())