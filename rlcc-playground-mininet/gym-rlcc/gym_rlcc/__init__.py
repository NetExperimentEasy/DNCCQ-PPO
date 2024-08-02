from gym.envs.registration import register

register(
    id="gym_rlcc/rlcc-v0",
    entry_point="gym_rlcc.envs:RlccEnv",
)

register(
    id="gym_rlcc/rlcc-v1",
    entry_point="gym_rlcc.envs:RlccEnvMulti",
)

register(
    id="gym_rlcc/rlcc-v0-rllib",
    entry_point="gym_rlcc.envs:RlccEnvR",
)

register(
    id="gym_rlcc/rlcc-v1-rllib",
    entry_point="gym_rlcc.envs:RlccEnvMultiR",
)

# qlearning tile xquic based
register(
    id="gym_rlcc/rlcc-v0-q",
    entry_point="gym_rlcc.envs:RlccEnvQ",
)

# qlearning tile Tcp netlink based
register(
    id="gym_rlcc/rlcc-v1-q",
    entry_point="gym_rlcc.envs:RlccEnvQT",
)

