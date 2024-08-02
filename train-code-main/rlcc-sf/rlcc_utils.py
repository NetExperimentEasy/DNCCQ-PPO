from typing import Optional

import gymnasium as gym
from gym_rlcc.envs import RlccEnv, RlccEnvMulti

from sample_factory.utils.utils import is_module_available


def rlcc_available():
    return is_module_available("gym_rlcc")


class RlccSpec:
    def __init__(self, name, env_class):
        self.name = name
        self.env_class = env_class


RLCC_ENVS = [
    RlccSpec("rlcc", RlccEnv), # rlcc xquic single step sample
    RlccSpec("rlcc_ms", RlccEnvMulti), # rlcc xquic multi step sample
    # add more
]


def rlcc_env_by_name(name):
    for cfg in RLCC_ENVS:
        if cfg.name == name:
            return cfg
    raise Exception("Unknown Rlcc env")


def make_rlcc_env(env_name, _cfg, _env_config, render_mode: Optional[str] = None, **kwargs):
    rlcc_spec = rlcc_env_by_name(env_name)
    # env = gym.make(rlcc_spec.env_id, render_mode=render_mode)
    env_class = rlcc_spec.env_class
    
    print(_env_config)
    """
    {'worker_index': 0, 'vector_index': 0, 'env_id': 0}
    """
    
    # 初始时，获取环境的obs和action特征，此时_env_config是None
    if _env_config is None:
        config = {"rlcc_flag" : 1000}
    else:
        config = {"rlcc_flag" : 1001+_env_config["env_id"]}
    # config["reward_function"] = 
    config["plan"] = 3
    config["maxsteps"] = 1800
    
    return env_class(config)


# rlcc params
def rlcc_override_defaults(env, parser):
    parser.set_defaults(
        # env_gpu_observations=False,
        env_gpu_actions=False,
        batched_sampling=False, #
        num_workers=8, # 8
        num_envs_per_worker=1, # 8
        worker_num_splits=1, # 2 : double-buffered sampling
        # train_for_env_steps=1800,
        train_for_seconds=120,
        encoder_mlp_layers=[64, 512, 256, 64], # [64, 64]
        env_frameskip=1,
        nonlinearity="tanh",
        batch_size=1024, # 1024
        kl_loss_coeff=0.1,
        use_rnn=False,  # add RNN ?
        adaptive_stddev=False,
        policy_initialization="torch_default",
        reward_scale=1,
        max_grad_norm=3.5,
        ppo_clip_ratio=0.2,
        value_loss_coeff=1.3,
        exploration_loss_coeff=0.0,
        learning_rate=0.00295,
        lr_schedule="linear_decay",
        shuffle_minibatches=False,
        rollout=64,  # 64 rollout? rollout step < env steps always
        gamma=0.99,
        gae_lambda=0.95,
        with_vtrace=False,
        recurrence=1,
        normalize_input=True, #
        normalize_returns=True, #
        value_bootstrap=True,
        experiment_summaries_interval=3,
        save_every_sec=120,  #
        serial_mode=False,  # 
        async_rl=True,  # False

        decorrelate_experience_max_seconds=100
    )


# add more rlcc env args
def add_rlcc_env_args(env, parser):
    # add more args in the future
    pass