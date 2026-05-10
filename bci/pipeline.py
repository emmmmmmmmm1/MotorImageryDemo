from __future__ import annotations

import numpy as np

from .models.base import BaseDecoder
from .preprocessing import Preprocessor
from .smoother import BaseSmoother


class InferencePipeline:
    """Realtime inference glue.

    The window passed to :meth:`predict_window` is assumed to be already
    filtered (the EEGReceiver thread runs `Preprocessor.transform_chunk`
    upstream), so this class never calls `transform_chunk` itself. That
    is what lets calibration and realtime distributions match without
    re-introducing a per-window filter transient.
    """

    def __init__(
        self,
        pre: Preprocessor,
        decoder: BaseDecoder,
        smoother: BaseSmoother,
    ) -> None:
        self.pre = pre
        self.decoder = decoder
        self.smoother = smoother

    def predict_window(self, window: np.ndarray) -> np.ndarray:
        arr = np.asarray(window)
        if arr.ndim == 2:
            arr = arr[None, ...]  # (1, ch, samples)
        elif arr.ndim != 3 or arr.shape[0] != 1:
            raise ValueError(
                f"window must be (ch, samples) or (1, ch, samples); "
                f"got {arr.shape}"
            )
        proba = self.decoder.predict_proba(arr)[0]
        return self.smoother.update(proba)

    def reset_smoother(self) -> None:
        self.smoother.reset()
