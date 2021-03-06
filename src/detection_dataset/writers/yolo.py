import os
import shutil

import pandas as pd
from joblib import Parallel, delayed
from ruamel.yaml import YAML

from detection_dataset.writers import BaseWriter

yaml = YAML()

YAML_TEMPLATE = """
path: {path}
train: images/train
val: images/val
test:  images/test

# Classes
nc: {n_classes}
names: [{class_names}]
"""


class YoloWriter(BaseWriter):
    """Writes a dataset to a directory in the YOLO format."""

    format = "yolo"

    def __init__(self, **kwargs) -> None:
        """Initializes the YoloWriter."""

        super().__init__(**kwargs)
        self.data["bbox"] = [[bbox.to_yolo() for bbox in bboxes] for bboxes in self.data.bbox]

    def write_to_disk(self) -> None:
        """Writes the dataset to disk.

        For the YOLO format, the associated steps are:
            1. Write the YAML file.
            2. Create the directories for the images and labels.
            3. Write the images and labels.
        """

        self._write_yaml()

        for split in self.data.split.unique():
            self._make_dirs(split)

            split_data = self.data[self.data.split == split]
            self._write_images_labels_parallel(split_data)

    def _write_yaml(self) -> None:
        """Writes the YAML file for the dataset.

        In the YOLO format, this file contains the path to the images, the names of the classes, and the number of
        classes.
        """

        os.makedirs(self.dataset_dir)

        yaml_template_formated = YAML_TEMPLATE.format(
            path=self.dataset_dir,
            n_classes=self.n_classes,
            class_names=", ".join(self.class_names),
        )

        yaml_dataset = yaml.load(yaml_template_formated)

        with open(os.path.join(self.dataset_dir, "dataset.yml"), "w") as outfile:
            yaml.dump(yaml_dataset, outfile)

    def _make_dirs(self, split: str) -> None:
        """Creates the directories (images, labels) for the given split.

        Args:
            split: The split to create the directories for (train, val, test).
        """

        os.makedirs(os.path.join(self.dataset_dir, "images", split))
        os.makedirs(os.path.join(self.dataset_dir, "labels", split))

    def _write_images_labels_parallel(self, split_data: pd.DataFrame) -> None:
        """Wraps _write_images_labels for parallelization.

        Args:
            split_data: The data to write corresponding to a single split.
        """

        Parallel()(delayed(self._write_images_labels)(row) for _, row in split_data.iterrows())

    def _write_images_labels(self, row: pd.DataFrame) -> None:
        """Writes the images and labels for a single image.

        Args:
            row: The row of the dataframe to write.
        """

        row = row.to_frame().T

        # Images
        in_file = row.image_path.values[0]
        out_file = self._get_filename(row, "images")

        shutil.copyfile(in_file, out_file)

        # Labels
        out_file = self._get_filename(row, "labels")
        data = row.explode(["bbox_id", "category_id", "area", "bbox"])

        with open(out_file, "w") as f:
            for _, r in data.iterrows():
                labels = " ".join((str(r.category_id), str(r.bbox[0]), str(r.bbox[1]), str(r.bbox[2]), str(r.bbox[3])))
                f.write(labels + "\n")

    def _get_filename(self, row: pd.Series, task: str) -> str:
        """Returns the filename for the given row and task.

        Args:
            row: The row of the dataframe to write.
            task: The task to get the filename for (images, labels).

        Returns:
            The filename for the given row and task.

        Raises:
            ValueError: If the task is not images or labels.
        """

        split = row.split.values[0]
        image_id = str(row.image_id.values[0])

        if task == "labels":
            return os.path.join(self.dataset_dir, "labels", split, image_id + ".txt")
        elif task == "images":
            return os.path.join(self.dataset_dir, "images", split, image_id + ".jpg")
        else:
            raise ValueError(f"tTask must be either 'lables' or 'images', not {task}")
