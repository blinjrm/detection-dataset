from abc import ABC, abstractmethod
from typing import Dict, Tuple

import pandas as pd


class BaseReader(ABC):
    def __init__(self, path: str, splits: Dict[str, Tuple[str, str]]) -> None:
        """Base class for loading datasets in memory.

        Args:
            path: Path to the dataset
        """

        self.path = path
        self.splits = splits
        # self._data, self.categories = self._load()
        self.dataset = self._load()

    @abstractmethod
    def _load(self) -> pd.DataFrame:
        """Load a dataset.

        Returns:
            A pandas DataFrame containing the dataset.
        """

    @property
    def data(self) -> pd.DataFrame:
        """Access the class data.

        Returns:
            A pandas DataFrame containing the dataset.
        """

        return self._data
