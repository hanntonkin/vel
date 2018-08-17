import cv2
import numpy as np
import os.path
import pathlib
import sys
import torch
import tqdm

from vel.api import ModelConfig
from vel.api.base import Storage, ModelFactory
from vel.rl.api.base import EnvFactory
from vel.openai.baselines.common.atari_wrappers import FrameStack


class RecordMovieCommand:
    """ Record environment playthrough as a game  """
    def __init__(self, model_config: ModelConfig, env_factory: EnvFactory, model_factory: ModelFactory,
                 storage: Storage, videoname: str, takes: int, frame_history: int, seed: int,
                 fps: int, sample_args: dict = None):
        self.model_config = model_config
        self.model_factory = model_factory
        self.env_factory = env_factory
        self.storage = storage
        self.takes = takes
        self.videoname = videoname
        self.frame_history = frame_history
        self.sample_args = sample_args if sample_args is not None else {}
        self.fps = fps

        self.seed = seed

    def run(self):
        device = torch.device(self.model_config.device)

        env = FrameStack(self.env_factory.instantiate(preset='raw'), self.frame_history)
        model = self.model_factory.instantiate(action_space=env.action_space).to(device)

        self.storage.resume_learning(model)

        model.eval()

        for i in range(self.takes):
            self.record_take(model, env, device, takenumber=i+1)

    @torch.no_grad()
    def record_take(self, model, env_instance, device, takenumber):
        frames = []

        observation = env_instance.reset()

        frames.append(env_instance.render('rgb_array'))

        print("Evaluating environment...")

        while True:
            observation_array = np.expand_dims(np.array(observation), axis=0)
            observation_tensor = torch.from_numpy(observation_array).to(device)
            actions = model.step(observation_tensor, **self.sample_args)['actions']

            observation, reward, done, epinfo = env_instance.step(actions.item())

            frames.append(env_instance.render('rgb_array'))

            if 'episode' in epinfo:
                # End of an episode
                break

        takename = self.model_config.output_dir('videos', self.model_config.run_name, self.videoname.format(takenumber))
        pathlib.Path(os.path.dirname(takename)).mkdir(parents=True, exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')
        video = cv2.VideoWriter(takename, fourcc, self.fps, (frames[0].shape[1], frames[0].shape[0]))

        for i in tqdm.trange(len(frames), file=sys.stdout):
            video.write(frames[i])

        video.release()
        print(f"Written {takename}")


def create(model_config, model, env, storage, takes, videoname, frame_history, seed=0, fps=30, sample_args=None):
    return RecordMovieCommand(
        model_config=model_config,
        model_factory=model,
        env_factory=env,
        storage=storage,
        videoname=videoname,
        frame_history=frame_history,
        takes=takes,
        seed=seed,
        fps=fps,
        sample_args=sample_args
    )