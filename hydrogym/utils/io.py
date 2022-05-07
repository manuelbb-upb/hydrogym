import numpy as np
import firedrake as fd
import pickle

from ..core import FlowConfig, CallbackBase
from .utils import print, is_rank_zero
from typing import Any, Optional, Callable, Tuple

__all__ = ['ParaviewCallback', 'CheckpointCallback', 'LogCallback', 'SnapshotCallback', 'GenericCallback']

class ParaviewCallback(CallbackBase):
    def __init__(self,
            interval: Optional[int] = 1,
            filename: Optional[str] = 'output/solution.pvd',
            postprocess: Optional[Callable] = None):
        super().__init__(interval=interval)
        self.file = fd.File(filename)

        # Postprocess will be called before saving (use to compute vorticity, for instance)
        self.postprocess = postprocess
        if self.postprocess is None:
            self.postprocess = lambda flow: (flow.u, flow.p)

    def __call__(self, iter: int, t: float, flow: FlowConfig):
        if super().__call__(iter, t, flow):
            state = self.postprocess(flow)
            if (iter % self.interval == 0):
                self.file.write(*state, time=t)

class CheckpointCallback(CallbackBase):
    def __init__(self,
            interval: Optional[int] = 1,
            filename: Optional[str] = 'output/checkpoint.h5'):
        super().__init__(interval=interval)
        self.filename = filename

    def __call__(self, iter: int, t: float, flow: Tuple[fd.Function]):
        if super().__call__(iter, t, flow):
            flow.save_checkpoint(self.filename)

class LogCallback(CallbackBase):
    def __init__(self,
            postprocess: Callable,
            nvals,
            interval: Optional[int] = 1,
            filename: Optional[str] = None,
            print_fmt: Optional[str] = None
            ):
        super().__init__(interval=interval)
        self.postprocess = postprocess
        self.filename = filename
        self.print_fmt = print_fmt
        self.data = np.zeros((1, nvals+1))

    def __call__(self, iter: int, t: float, flow: Tuple[fd.Function]):
        if super().__call__(iter, t, flow):
            new_data = np.array([t, *self.postprocess(flow)], ndmin=2)
            if iter==0:
                self.data[0, :] = new_data
            else:
                self.data = np.append(self.data, new_data, axis=0)

            if self.filename is not None and is_rank_zero():
                np.savetxt(self.filename, self.data)
            if self.print_fmt is not None:
                print(self.print_fmt.format(*new_data.ravel()))

class SnapshotCallback(CallbackBase):
    def __init__(self,
            interval: Optional[int] = 1,
            output_dir: Optional[str] = 'snapshots'
        ):
        """
        Save snapshots as checkpoints for modal analysis

        Note that this slows down the simulation
        """
        super().__init__(interval=interval)
        self.output_dir = output_dir
        self.snap_idx = 0
        self.saved_mesh = False

    def __call__(self, iter: int, t: float, flow: Tuple[fd.Function]):
        if iter == 0:
            flow.save_checkpoint(f'{self.output_dir}/checkpoint.h5')  # Save matrix
        if super().__call__(iter, t, flow):
            write_mesh = not self.saved_mesh
            flow.save_checkpoint(f'{self.output_dir}/{self.snap_idx}.h5', write_mesh=write_mesh)
            if write_mesh:
                self.saved_mesh=True
            self.snap_idx += 1

class GenericCallback(CallbackBase):
    def __init__(self,
            callback: Callable,
            interval: Optional[int] = 1):
        super().__init__(interval=interval)
        self.cb = callback
    
    def __call__(self, iter: int, t: float, flow: FlowConfig):
        if super().__call__(iter, t, flow):
            self.cb(iter, t, flow)