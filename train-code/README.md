#

本仓库为训练代码

/rllib：使用rllib库实现的训练代码。single为使用单步环境，multisteps使用的是多步采样环境。

由于rllib与tianshou框架的分布式训练机制所限(当然也可能是我没玩儿明白)，当前rllib为非分布式且单个环境训练。（即使是开了并行环境，采样也是非异步的，或者异步无法提供所需的分布式训练需求）


./rlcc-sf: sample-factory实现分布式训练环境代码