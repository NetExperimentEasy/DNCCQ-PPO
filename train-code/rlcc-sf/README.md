

# envs

`pip install sample-factory`

`pip install gymnasium`

`pip install wandb`

# Usage

`python train_rlcc.py --env=rlcc --experiment=testexp --device=cpu`

`wandb login`

`python train_rlcc.py --env=rlcc --experiment=base-aurora-reward --train_dir=./baseTrain --with_wandb=True --wandb_user=seclee --wandb_project rlcc-1step-8-drtt-aR --wandb_tags base rlcc batch8 1step doubleRtt auroraReward ppo --device=cpu`

https://www.samplefactory.dev/07-advanced-topics/profiling/?h=async#example-profiling-an-asynchronous-workload


`python train_rlcc.py --env=rlcc --experiment=base-aurora-new-reward --train_dir=./baseTrain --with_wandb=True --wandb_user=seclee --wandb_project rlcc-1step-8-drtt-anR --wandb_tags base rlcc batch8 1step doubleRtt auroraNewReward ppo`

python train_rlcc.py --env=rlcc --experiment=base-reward --train_dir=./baseTrain --with_wandb=True --wandb_user=seclee --wandb_project rlcc-1step-8-drtt-basereward --wandb_tags base rlcc batch8 1step doubleRtt baseReward ppo
